# ruff: noqa: E501
"""Rewrite questions in plain words and trim their rubric (round 3).

Round 2 (docs/evaluations/2026-10-bc-registries-v2/) found the questions
answerable by grep, because they carry the code's own names, and rubrics
that reward facts the question never asks for. For each question Opus
writes the question a newcomer would ask about the same behaviour, in the
domain's words only (no identifiers, file, class, function, table, queue or
endpoint names), and keeps the facts that question requires. The facts
themselves are unchanged: they stay verified.

Writes data/arch3.json: the same entries with `question` replaced, `facts`
trimmed, and `original` and `dropped` kept for the record.

Usage: python3 plain.py QID ...
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import common

PROMPT = """Below is a question about the BC Registries codebase (the British Columbia business registry) and the verified facts that answer it.

Rewrite the question as a developer new to the system would ask it, knowing the business domain but not the code:
- Use only domain words (business, filing, payment, invoice, account, team member, administrator, dashboard...). Do not use any identifier, file, class, function, method, variable, constant, table, queue, topic, endpoint or status-enum name, and no word in camelCase or snake_case.
- Ask about the same behaviour, at the same scope. Do not add hints about where it lives.
- One or two sentences.

Then list the facts the rewritten question really asks for: a fact is kept when a good answer to the question must state it, and dropped when it is a detail the question does not ask about (an internal helper, a side effect, a consumer the question does not mention).

Reply with only JSON: {{"question": "...", "keep": [fact numbers, 1-based]}}

QUESTION:
{question}

FACTS:
{facts}"""


def rewrite(q):
    facts = "\n".join(f"{i + 1}. {f['fact']}" for i, f in enumerate(q["facts"]))
    text = common.llm(
        PROMPT.format(question=q["question"], facts=facts),
        system="You write benchmark questions. Reply with JSON only.",
        model="opus",
        role="plain",
    )
    j = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
    keep = sorted({int(n) for n in j["keep"] if 1 <= int(n) <= len(q["facts"])})
    return {
        **q,
        "question": j["question"],
        "original": q["question"],
        "facts": [q["facts"][n - 1] for n in keep],
        "dropped": [
            q["facts"][n - 1]["fact"]
            for n in range(1, len(q["facts"]) + 1)
            if n not in keep
        ],
    }


def main(qids):
    qs = [
        q
        for q in json.loads((common.DATA / "arch.json").read_text())
        if q["qid"] in qids
    ]
    with ThreadPoolExecutor(5) as ex:
        out = list(ex.map(rewrite, qs))
    (common.DATA / "arch3.json").write_text(json.dumps(out, indent=2))
    for q in out:
        print(
            f"{q['qid']}: {len(q['facts'])} facts kept, {len(q['dropped'])} dropped\n  {q['question']}"
        )


if __name__ == "__main__":
    main(set(sys.argv[1:]))
