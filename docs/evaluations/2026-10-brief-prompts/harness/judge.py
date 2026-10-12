# ruff: noqa: E501 - report tables and SQL read best on one line
"""Score briefs against the architecture facts of the agents evaluation.

A fact (`../../2026-10-bc-registries-agents/data/arch.json`) is one verified
statement about how the system works, with the files it cites. A leaf is
scored on the facts that cite at least one of its files: for each, a judge
model reads the brief and says whether it conveys what this part does in
that fact (2 stated, 1 hinted or partial, 0 absent) and whether it
contradicts it. A second, mechanical score: of the leaf's files that facts
cite, how many the brief names (an agent finds the file to open).

Writes `<out>/leaf-<id>/judge.md` and returns per-prompt scores.

Usage: uv run python judge.py DB ASSIGNMENT LEAF OUT CACHE
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
from pilot import BRIEF_MODEL, Models, _members

ARCH = Path(__file__).parents[2] / "2026-10-bc-registries-agents/data/arch.json"

JUDGE = """\
Below is a description of one part of a software system, then numbered \
facts about how the system works. Each fact lists which of its files belong \
to this part. For each fact, judge only what this part does in it - what \
those files do - and whether a reader of the description alone would know \
it:
- 2: the description states it (in any words; exact names not required \
where the meaning is clear);
- 1: the description hints at it or states part of it;
- 0: absent.
Also mark "wrong": true when the description says something that \
contradicts the fact.

Reply with only a JSON list, one object per fact: \
[{{"n": 1, "score": 2, "wrong": false}}, ...]

DESCRIPTION:
{brief}

FACTS:
{facts}"""


NOISE = """\
Below is a description of one part of a software system, as numbered \
lines. Label each line:
- "core": a reader needs it to understand the part's role or to find \
where to change it - what it does, what reaches it and what it sends out, \
a decision that shapes its behaviour, a hazard that loses or corrupts work, \
where to look;
- "detail": true but minor or obvious - setup and wiring, configuration, \
lists of fields or values, test plumbing, logging, trivia.
Headings get "core".

Reply with only a JSON list of labels, one per line, in order: \
["core", "detail", ...]

{lines}"""


def noise(models: Models, brief: str) -> float:
    """Share of the brief's words on lines a judge calls detail."""
    lines = [line for line in brief.splitlines() if line.strip()]
    numbered = "\n".join(f"{n}. {line}" for n, line in enumerate(lines, 1))
    reply = models.ask(BRIEF_MODEL, NOISE.format(lines=numbered))
    labels = _first_list(reply)
    words = [len(line.split()) for line in lines]
    detail = sum(
        w for w, lab in zip(words, labels, strict=False) if lab == "detail"
    )
    return round(detail / sum(words), 2)


def leaf_facts(files: set[str]) -> list[dict]:
    facts = []
    for question in json.loads(ARCH.read_text()):
        for fact in question["facts"]:
            here = [f for f in fact["files"] if f in files]
            if here:
                facts.append({"fact": fact["fact"], "here": here})
    return facts


def score(models: Models, brief: str, facts: list[dict], run: int = 0) -> dict:
    listed = "\n".join(
        f"{n}. {f['fact']}\n   Files in this part: {', '.join(f['here'])}"
        for n, f in enumerate(facts, 1)
    )
    prompt = JUDGE.format(brief=brief, facts=listed)
    # A repeat run differs by a trailing marker only, so it misses the cache.
    reply = models.ask(BRIEF_MODEL, prompt + "\n" * run)
    verdicts = _first_list(reply)
    cited = {f for fact in facts for f in fact["here"]}
    named = {f for f in cited if Path(f).name in brief or _tail(f) in brief}
    return {
        "facts": round(sum(v["score"] for v in verdicts) / (2 * len(facts)), 2),
        "wrong": sum(1 for v in verdicts if v.get("wrong")),
        "files_named": f"{len(named)}/{len(cited)}",
        "verdicts": verdicts,
    }


def _first_list(reply: str) -> list:
    """The first JSON list in a reply, ignoring anything after it."""
    return json.JSONDecoder().raw_decode(reply[reply.index("[") :])[0]


def _tail(path: str) -> str:
    return "/".join(Path(path).parts[-2:])


def main(db_path, assignment, leaf, out, cache) -> None:
    sections = _members(db_path, np.load(assignment), int(leaf))
    files = {s["source"] + "/" + s["path"] for s in sections}
    facts = leaf_facts(files)
    out_dir = Path(out) / f"leaf-{leaf}"
    briefs = _read_briefs(out_dir / "briefs.md")
    # The ceiling: the condensations a brief is written from, judged as one.
    briefs["(input)"] = (out_dir / "input.md").read_text()
    models = Models(Path(cache))
    runs = int(os.environ.get("JUDGE_RUNS", "1"))
    noisy = set(os.environ.get("JUDGE_NOISE", "").split(","))
    results = {}
    for name, text in briefs.items():
        scored = [score(models, text, facts, run) for run in range(runs)]
        results[name] = scored[0] | {
            "facts": round(sum(r["facts"] for r in scored) / runs, 2),
            "detail": noise(models, text) if name in noisy else "",
            "spread": f"{min(r['facts'] for r in scored)}-{max(r['facts'] for r in scored)}",
        }
    models.save()
    print(f"{models.calls} new model calls")
    lines = [
        f"{len(facts)} facts cite this leaf's files.\n",
        "| prompt | words | facts conveyed | runs' range | detail share "
        "| contradicted | cited files named |",
        "|---|---|---|---|---|---|---|",
        *(
            f"| `{n}` | {len(briefs[n].split())} | {r['facts']} | {r['spread']} "
            f"| {r['detail']} | {r['wrong']} | {r['files_named']} |"
            for n, r in results.items()
        ),
        "",
        "Per fact (score per prompt):\n",
        "| # | fact | " + " | ".join(results) + " |",
        "|---|---|" + "---|" * len(results),
    ]
    for i, fact in enumerate(facts):
        cells = " | ".join(
            str(r["verdicts"][i]["score"]) for r in results.values()
        )
        lines.append(f"| {i + 1} | {fact['fact'][:110]}… | {cells} |")
    (out_dir / "judge.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[: 4 + len(results)]))


def _read_briefs(path: Path) -> dict[str, str]:
    """`briefs.md` back into {prompt: brief}; prompt names are `# name` lines."""
    names = set(json.loads((path.parent / "prompts.json").read_text()))
    briefs, current = {}, None
    for line in path.read_text().splitlines():
        if line.startswith("# ") and line[2:].strip() in names:
            current = line[2:].strip()
            briefs[current] = []
        elif current:
            briefs[current].append(line)
    return {n: "\n".join(b).strip() for n, b in briefs.items()}


if __name__ == "__main__":
    main(*sys.argv[1:6])
