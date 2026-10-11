# ruff: noqa: E501, E741, B904, B905, B023, E402, SIM115
"""Score the arms.

locate: judge-free. Predicted paths against the files the real commit
modified (pre-existing, non-test): recall, precision, F1.
arch: Opus judges, blind to the arm, how many of the reference key facts the
answer states (1 covered, 0.5 partial, 0 missing or wrong), and counts claims
that contradict the code as the facts describe it.
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import common

JUDGE = """You grade an answer to a question about a codebase against a reference list of key facts verified in the code.

Question:
{question}

Reference key facts:
{facts}

Candidate answer:
{answer}

For each key fact, give 1 if the answer states it (same components or clearly equivalent ones; exact wording and paths need not match), 0.5 if it is partly stated or vague (the right area but a key component missing), 0 if it is missing or contradicted. Then count "errors": statements in the answer that contradict a key fact. Do not reward length.

Reply with only JSON: {{"facts": [<score per fact in order>], "errors": <int>}}"""


def paths(text):
    m = re.search(r"\[.*\]", text, re.S)
    try:
        got = json.loads(m.group(0)) if m else []
    except ValueError:
        got = re.findall(r"[\w./-]+\.\w+", text)
    return [str(p).strip().lstrip("./") for p in got if isinstance(p, str)][:12]


def locate(row, q):
    truth = {f"{q['repo']}/{p}" for p in q["modified"]}
    pred = paths(row["answer"])
    hit = [p for p in pred if p in truth]
    rec = len(hit) / len(truth)
    prec = len(hit) / len(pred) if pred else 0.0
    f1 = 2 * rec * prec / (rec + prec) if rec + prec else 0.0
    return {
        "recall": rec,
        "precision": prec,
        "f1": f1,
        "n_pred": len(pred),
        "n_truth": len(truth),
    }


def arch(row, q):
    facts = "\n".join(f"{i + 1}. {f['fact']}" for i, f in enumerate(q["facts"]))
    text = common.llm(
        JUDGE.format(
            question=q["question"],
            facts=facts,
            answer=row["answer"] or "(no answer)",
        ),
        system="You are a strict, fair grader. Reply with JSON only.",
        model="opus",
        role="judge",
    )
    j = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    s = [float(x) for x in j["facts"]][: len(q["facts"])]
    return {
        "coverage": sum(s) / len(q["facts"]),
        "fact_scores": s,
        "errors": int(j.get("errors", 0)),
    }


def main(kind, arms):
    qs = {q["qid"]: q for q in json.load(open(common.DATA / f"{kind}.json"))}
    for arm in arms:
        rows = [
            json.loads(l) for l in open(common.RUNS / f"{kind}-{arm}.jsonl")
        ]
        fn = locate if kind == "locate" else arch
        with ThreadPoolExecutor(6) as ex:
            scores = list(ex.map(lambda r: fn(r, qs[r["qid"]]), rows))
        with open(common.RUNS / f"{kind}-{arm}.scores.jsonl", "w") as f:
            for r, s in zip(rows, scores):
                f.write(json.dumps({"qid": r["qid"], "arm": arm, **s}) + "\n")
        print(kind, arm, len(scores))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
