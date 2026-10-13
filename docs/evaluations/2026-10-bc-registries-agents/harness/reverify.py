# ruff: noqa: E501
"""Re-verify a question set's facts, strictly, before grading with them.

The hard-question analysis found a fact stating the opposite of the code
(the fee-waiver question: a non-staff waiver IS refused when the charge is
created). A fresh Opus agent re-reads the code for every fact, looking for
the code that would contradict it, and either keeps it, corrects it, or
drops it. Rewrites data/<set>.json in place, keeping the old facts as
`facts_before`.

A question already re-verified is kept as it is.

Usage: python3 reverify.py SET
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import common

PROMPT = """You are auditing one question of a benchmark against the code. The current directory holds four BC Registries repositories (lear/, sbc-auth/, sbc-pay/, business-filings-ui/).

For each fact below, try hard to prove it WRONG: read the cited files and search for any other code (another check, another caller, a guard, a test asserting the opposite) that contradicts or limits it. A fact is "correct" only if it survives that. If it is partly right, give the corrected fact, stating only what the code shows.

QUESTION: {question}

FACTS:
{facts}

Reply with only JSON: [{{"verdict": "correct|partly|wrong", "fix": "<corrected fact if partly, else empty>", "why": "<one line: the code that settles it>"}}, ...one per fact in order]"""


def check(q):
    if "reverdicts" in q:  # already re-verified
        return q
    facts = "\n".join(
        f"{i + 1}. {f['fact']} (files: {', '.join(f['files'])})"
        for i, f in enumerate(q["facts"])
    )
    r = common.run_agent(
        PROMPT.format(question=q["question"], facts=facts),
        model="opus",
        role="reverify",
        key=q["qid"],
        max_turns=80,
        tools=["Read", "Grep", "Glob"],
        timeout=3600,
    )
    verdicts = json.loads(re.search(r"\[.*\]", r["answer"], re.S).group(0))
    kept = []
    for f, v in zip(q["facts"], verdicts, strict=False):
        if v["verdict"] == "correct":
            kept.append(f)
        elif v["verdict"] == "partly" and v.get("fix"):
            kept.append({**f, "fact": v["fix"], "fixed": True})
    print(q["qid"], [v["verdict"] for v in verdicts], flush=True)
    return {
        **q,
        "facts": kept,
        "facts_before": q["facts"],
        "reverdicts": verdicts,
    }


def main(name):
    path = common.DATA / f"{name}.json"
    qs = json.loads(path.read_text())
    with ThreadPoolExecutor(5) as ex:
        out = list(ex.map(check, qs))
    path.write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
