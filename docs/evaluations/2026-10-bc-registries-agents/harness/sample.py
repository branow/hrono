# ruff: noqa: E501, SIM115
"""Draw the 40 change-localization items from the described commits (seed 0)."""

import json
import random

import common

QUOTA = {"lear": 14, "sbc-auth": 11, "sbc-pay": 11, "business-filings-ui": 4}

if __name__ == "__main__":
    rows = json.load(open(common.DATA / "described.json"))
    pool = [
        r for r in rows if r["verdict"] == "KEEP" and len(r["modified"]) >= 4
    ]
    rnd = random.Random(0)
    out = []
    for repo, n in QUOTA.items():
        mine = [r for r in pool if r["repo"] == repo]
        rnd.shuffle(mine)
        out += mine[:n]
    for i, r in enumerate(out):
        r["qid"] = f"loc-{i:02d}"
    json.dump(out, open(common.DATA / "locate.json", "w"), indent=1)
