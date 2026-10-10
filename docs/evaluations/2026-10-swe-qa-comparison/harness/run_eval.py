# ruff: noqa: E501, E741, B904, B905, B007, B023
"""Answer every question with every system, then judge every answer.

    uv run python run_eval.py answer hrono bm25 ...   # writes runs/answers/<system>.jsonl
    uv run python run_eval.py judge  hrono bm25 ...   # writes runs/judgments/<system>.jsonl

Both steps resume: a question already in the output file is skipped.

Controls that hold across systems:
- the same questions (SWE-QA, all 48 per repository), the same pinned commits;
- the same answer model, system prompt and answer template;
- the same context cap: at most 8000 characters of retrieved context, ranked
  chunks taken in order (hrono's recall returns at most 10 passages of about
  800 B, which the cap was sized to; it may return fewer, and that is its own
  behavior);
- the same judge: SWE-QA's own LLM-as-a-judge prompt, read verbatim from the
  benchmark's script, which sees only question, reference and candidate.
"""

from __future__ import annotations

import json
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import common
import retrievers

ANSWERS = common.RUNS / "answers"
JUDGMENTS = common.RUNS / "judgments"
WIDTH = 8

SYSTEM = (
    "You are a professional code analysis assistant, you are good at "
    "explaining code and answering programming questions."
)

WITH_CONTEXT = """Repository: {repo} (a Python project on GitHub)

The following excerpts were retrieved from the repository:

{context}

Question: {question}

Answer the question about this repository. Ground the answer in the excerpts where they are relevant and name the files, classes and functions involved. Be precise; at most 300 words."""

WITHOUT_CONTEXT = """Repository: {repo} (a Python project on GitHub)

Question: {question}

Answer the question about this repository and name the files, classes and functions involved. Be precise; at most 300 words."""

_lock = threading.Lock()


def _done(path) -> set[str]:
    if not path.exists():
        return set()
    return {json.loads(line)["qid"] for line in path.open()}


def _append(path, row):
    with _lock, path.open("a") as f:
        f.write(json.dumps(row) + "\n")


def answer(system_name: str) -> None:
    system = retrievers.SYSTEMS[system_name]()
    out = ANSWERS / f"{system_name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = _done(out)
    todo = [
        q
        for repo in common.REPO_NAMES
        for q in common.questions(repo)
        if q["qid"] not in done
    ]

    def one(q):
        t0 = time.time()
        chunks = system.retrieve(q["repo"], q["question"])
        t_ret = time.time() - t0
        if system_name == "closed-book":
            context = ""
            prompt = WITHOUT_CONTEXT.format(
                repo=q["repo"], question=q["question"]
            )
        else:
            context = common.fit_budget(chunks, common.CONTEXT_BUDGET)
            prompt = WITH_CONTEXT.format(
                repo=q["repo"], context=context, question=q["question"]
            )
        text = common.llm(
            prompt,
            system=SYSTEM,
            model=common.ANSWER_MODEL,
            role=f"answer:{system_name}",
        )
        _append(
            out,
            {
                "qid": q["qid"],
                "repo": q["repo"],
                "system": system_name,
                "question": q["question"],
                "answer": text,
                "context": context,
                "context_chars": len(context),
                "labels": [c[0] for c in chunks],
                "retrieve_seconds": round(t_ret, 3),
            },
        )

    run(one, todo, f"answer {system_name}")


def _judge_template() -> str:
    src = (
        common.ROOT
        / "SWE-QA-Bench"
        / "Benchmark construction"
        / "score"
        / "llm-as-a-judge.py"
    ).read_text()
    body = src.split('prompt = f"""', 1)[1].split('"""', 1)[0]
    return body


JUDGE_KEYS = [
    "correctness",
    "completeness",
    "relevance",
    "clarity",
    "reasoning",
]


def _parse(text: str):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        s = json.loads(m.group(0))
    except ValueError:
        return None
    if all(isinstance(s.get(k), int) and 1 <= s[k] <= 20 for k in JUDGE_KEYS):
        return {k: s[k] for k in JUDGE_KEYS}
    return None


def judge(system_name: str) -> None:
    template = _judge_template()
    refs = {q["qid"]: q for r in common.REPO_NAMES for q in common.questions(r)}
    src = ANSWERS / f"{system_name}.jsonl"
    out = JUDGMENTS / f"{system_name}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = _done(out)
    rows = [json.loads(line) for line in src.open()]
    todo = [r for r in rows if r["qid"] not in done]

    def one(row):
        q = refs[row["qid"]]
        prompt = (
            template.replace("{question}", q["question"])
            .replace("{reference}", q["reference"])
            .replace("{candidate}", row["answer"])
            .replace("{{", "{")
            .replace("}}", "}")
        )
        scores = None
        for attempt in range(3):
            text = common.llm(
                prompt + ("" if attempt == 0 else f"\n(retry {attempt})"),
                system="You are a strict evaluator.",
                model=common.JUDGE_MODEL,
                role="judge",
            )
            scores = _parse(text)
            if scores:
                break
        _append(
            out,
            {
                "qid": row["qid"],
                "repo": row["repo"],
                "system": system_name,
                "scores": scores,
                "total": sum(scores.values()) if scores else None,
            },
        )

    run(one, todo, f"judge {system_name}")


def run(fn, items, what):
    print(f"{what}: {len(items)} to do", flush=True)
    errors = 0
    with ThreadPoolExecutor(WIDTH) as pool:
        for i, fut in enumerate([pool.submit(fn, x) for x in items], 1):
            try:
                fut.result()
            except Exception as exc:  # keep going; a rerun retries it
                errors += 1
                print(f"  error: {exc!r}"[:300], flush=True)
            if i % 12 == 0:
                print(f"  {what}: {i}/{len(items)}", flush=True)
    print(f"{what}: finished, {errors} errors", flush=True)


if __name__ == "__main__":
    step, names = sys.argv[1], sys.argv[2:]
    for n in names:
        (answer if step == "answer" else judge)(n)
