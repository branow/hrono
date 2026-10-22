# ruff: noqa: E501, SIM115, E741, B905
"""Re-judge only the questions whose reference facts changed; keep the rest."""

import json
import sys
from concurrent.futures import ThreadPoolExecutor

import common
import score

kind, changed, arms = sys.argv[1], set(sys.argv[2].split(",")), sys.argv[3:]
qs = {q["qid"]: q for q in json.load(open(common.DATA / f"{kind}.json"))}
for arm in arms:
    old = {
        json.loads(l)["qid"]: json.loads(l)
        for l in open(common.RUNS / f"{kind}-{arm}.scores-before-audit.jsonl")
    }
    rows = [json.loads(l) for l in open(common.RUNS / f"{kind}-{arm}.jsonl")]
    todo = [r for r in rows if r["qid"] in changed]
    with ThreadPoolExecutor(6) as ex:
        new = dict(
            zip(
                [r["qid"] for r in todo],
                ex.map(lambda r: score.arch(r, qs[r["qid"]]), todo),
            )
        )
    with open(common.RUNS / f"{kind}-{arm}.scores.jsonl", "w") as f:
        for r in rows:
            s = (
                {"qid": r["qid"], "arm": arm, **new[r["qid"]]}
                if r["qid"] in new
                else old[r["qid"]]
            )
            f.write(json.dumps(s) + "\n")
    print(arm, "rejudged", len(new))
