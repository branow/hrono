# ruff: noqa: B905 - experiment harness
"""Where each answer claim is lost: raw source -> stored condensation
(notes-v3) -> stored leaf brief and its upper brief (A-v3)."""

import sys

import exp

ARMS = (
    sys.argv[2].split(",") if len(sys.argv) > 2 else ["raw", "notes-v3", "A-v3"]
)


def table(qids: list[str]) -> None:
    split = exp.load("claims.json")
    got = {
        (r["qid"], r["fact"], r["claim"], r["arm"]): r
        for r in exp.load("judge2-main.json")
    }
    lost = {a: 0 for a in ARMS}
    for qid in qids:
        print("==", qid)
        for f in split[qid]["structured"]["facts"]:
            for i, cl in enumerate(f["claims"]):
                marks = []
                for a in ARMS:
                    r = got.get((qid, f["fact"], i, a))
                    marks.append(
                        "?" if r is None else "Y" if r.get("stated") else "."
                    )
                print(f["fact"], i, " ".join(marks), cl["kind"][0], cl["claim"])
                for a, m in zip(ARMS, marks):
                    lost[a] += m == "Y"
    print("stated", lost)


if __name__ == "__main__":
    table(sys.argv[1].split(","))
