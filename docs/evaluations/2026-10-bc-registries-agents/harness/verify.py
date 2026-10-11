# ruff: noqa: E501, E741, B904, B905, B023, E402, SIM115
"""Check every reference fact against the code before it is used to grade.

A fresh Opus agent (not the one that wrote them) reads the cited files for
each fact and marks it correct, partly correct or wrong. Wrong facts are
dropped, partly correct ones replaced by the agent's corrected wording, and a
question left with fewer than four facts is dropped. Cited paths that do not
exist are removed.
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import common

PROMPT = """You are auditing a benchmark's reference answers against the code. The current directory holds four BC Registries repositories (lear/, sbc-auth/, sbc-pay/, business-filings-ui/).

For each question below, check every fact against the cited files (and anything else you need). Be strict: a fact is "correct" only if the code shows it as stated.

{items}

Reply with only JSON: {{"<qid>": [{{"verdict": "correct|partly|wrong", "fix": "<corrected fact if partly, else empty>"}}, ...one per fact in order], ...}}"""


def verify(area):
    qs = json.load(open(common.DATA / f"gen-{area}.json"))["questions"]
    for q in qs:
        for f in q["facts"]:
            f["files"] = [p for p in f["files"] if (common.CORPUS / p).exists()]
    items = json.dumps(
        [
            {"qid": q["qid"], "question": q["question"], "facts": q["facts"]}
            for q in qs
        ],
        indent=1,
    )
    r = common.run_agent(
        PROMPT.format(items=items),
        model="opus",
        role="verify",
        key=area,
        max_turns=120,
        tools=["Read", "Grep", "Glob"],
        timeout=5400,
    )
    v = json.loads(re.search(r"\{.*\}", r["answer"], re.S).group(0))
    kept = []
    for q in qs:
        facts = []
        for f, x in zip(q["facts"], v.get(q["qid"], [])):
            if x["verdict"] == "correct":
                facts.append(f)
            elif x["verdict"] == "partly" and x.get("fix"):
                facts.append({**f, "fact": x["fix"], "fixed": True})
        q["verdicts"] = v.get(q["qid"], [])
        q["facts"] = facts
        if len(facts) >= 4:
            kept.append(q)
    print(area, len(qs), "->", len(kept), r["usage"]["cost_usd"], flush=True)
    return kept, qs


if __name__ == "__main__":
    areas = sys.argv[1:]
    with ThreadPoolExecutor(3) as ex:
        res = list(ex.map(verify, areas))
    for area, (kept, allq) in zip(areas, res):
        json.dump(
            {"kept": kept, "all": allq},
            open(common.DATA / f"verified-{area}.json", "w"),
            indent=1,
        )
