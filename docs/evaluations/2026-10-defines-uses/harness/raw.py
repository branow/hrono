"""The true ceiling: the raw source of the fact's cited files, judged
against the same claims. One run."""

import exp
from exp import c, sl

conn = c.connect()
body: dict[str, list[str]] = {}
for source, path, text in conn.execute(
    "SELECT s.source, s.path, ct.body FROM sections s "
    "JOIN contents ct USING (content_hash) ORDER BY s.source, s.path, s.ordinal"
):
    body.setdefault(f"{source}/{path}", []).append(
        text.decode() if isinstance(text, bytes) else text
    )
split = exp.load("claims.json")
jobs = []
for q in sl.questions():
    for f in split[q["qid"]]["structured"]["facts"]:
        fact = q["facts"][f["fact"]]
        listing = "\n".join(
            f"{i}. {cl['claim']}" for i, cl in enumerate(f["claims"])
        )
        pages = "\n\n".join(
            f"--- {p} ---\n" + "\n".join(body.get(p, [])) for p in fact["files"]
        )
        prompt = exp.JUDGE.format(claims=listing, pages=pages).replace(
            "a map of a software system",
            "the source files of a software system",
        )
        jobs.append((q["qid"], f["fact"], prompt))


def one(job):
    qid, fact, prompt = job
    got = exp.ask(prompt, exp.SONNET, exp.VERDICTS)
    return {
        "qid": qid,
        "fact": fact,
        "arm": "raw",
        "verdicts": (got.get("structured") or {}).get("verdicts"),
        "error": got.get("error"),
        "cost": got.get("cost"),
    }


rows = [r for r in exp.load("judged-r1.json") if r["arm"] != "raw"]
new = list(exp.run_pool(one, jobs, 6))
print(
    "errors",
    sum(1 for r in new if not r["verdicts"]),
    "cost",
    round(sum(r["cost"] or 0 for r in new), 2),
)
exp.save("judged-r1.json", rows + new)
