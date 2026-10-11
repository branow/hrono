# ruff: noqa: E501, E741, B904, B905, B023, E402, SIM115
"""Floor: the same model answers the architecture questions with no tools at all.

On a codebase no model was trained on, this should be low; it is the
memorization check the SWE-QA run lacked.
"""

import json
from concurrent.futures import ThreadPoolExecutor

import common
import run_arms


def one(q):
    prompt = run_arms.ARCH.format(question=q["question"]).replace(
        "Investigate with your tools as much as you need, then reply",
        "You have no tools. Reply",
    )
    a = common.llm(
        prompt, system=run_arms.SYSTEM, model=run_arms.MODEL, role="arch:none"
    )
    return {
        "qid": q["qid"],
        "set": "arch",
        "arm": "none",
        "answer": a,
        "tools": [],
        "usage": {
            "num_turns": 1,
            "seconds": 0,
            "output_tokens": 0,
            "cache_read": 0,
            "cache_creation": 0,
            "input_tokens": 0,
            "cost_usd": 0,
        },
    }


if __name__ == "__main__":
    qs = run_arms.items("arch")
    with ThreadPoolExecutor(6) as ex:
        rows = list(ex.map(one, qs))
    with open(common.RUNS / "arch-none.jsonl", "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
