"""The ceiling with the stored v3 condensations, to see whether asking for
defines and uses cost the notes detail."""

import sys

import exp
from exp import c, sl

conn = c.connect()
secs: dict[str, list[int]] = {}
for sid, source, path in conn.execute("SELECT id, source, path FROM sections"):
    secs.setdefault(f"{source}/{path}", []).append(sid)
split = exp.load("claims.json")
jobs = []
for q in sl.questions():
    for f in split[q["qid"]]["structured"]["facts"]:
        fact = q["facts"][f["fact"]]
        listing = "\n".join(
            f"{i}. {cl['claim']}" for i, cl in enumerate(f["claims"])
        )
        notes = [
            f"--- {p} ---\n{exp.stored_condensation(conn, s)}"
            for p in fact["files"]
            for s in secs.get(p, [])
        ]
        jobs.append(
            (
                q["qid"],
                f["fact"],
                exp.JUDGE.format(claims=listing, pages="\n\n".join(notes)),
            )
        )


def one(job):
    qid, fact, prompt = job
    got = exp.ask(prompt, exp.SONNET, exp.VERDICTS)
    return {
        "qid": qid,
        "fact": fact,
        "arm": "notes-v3",
        "verdicts": (got.get("structured") or {}).get("verdicts"),
        "cost": got.get("cost"),
    }


run = sys.argv[1]
rows = exp.load(f"judged-{run}.json")
rows += list(exp.run_pool(one, jobs, 8))
exp.save(f"judged-{run}.json", rows)
print(
    run,
    "cost",
    round(sum(r["cost"] or 0 for r in rows if r["arm"] == "notes-v3"), 2),
)
