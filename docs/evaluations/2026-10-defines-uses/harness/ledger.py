# ruff: noqa: E501 - experiment harness; prompts read best whole
"""Round 2: a condense prompt that keeps what the notes drop.

The stored v3 notes of the exact cited files state under half the claims.
What they miss: exact lists a decision checks, each branch's condition, what
each error handler does, and the order of saves and calls. The `ledger`
prompt asks for those verbatim, with no word target. It runs on the 100
sections of the cited files only, and is scored with the same claims as the
notes ceiling (arm `notes-<variant>`).

Usage: uv run --with claude-agent-sdk python ledger.py condense
       uv run --with claude-agent-sdk python ledger.py judge r1|r2
"""

from __future__ import annotations

import sys

import exp
from exp import c, sl

LEDGER = """Condense this content chunk into notes a reader uses instead of the chunk: they must be able to answer exact questions about its behaviour from your notes alone.

Start with one sentence saying what it is for, in the terms of the system it belongs to (for example "Applies a confirmed payment to its business filing"). If it is a test, fixture, configuration, build file, migration or documentation, say so and name what it serves.

Then, for code, keep every one of these that the chunk has, each on its own line:
- ENTRY: each route, handler, listener, job or public function: who may call it and the exact check that guards it (what it compares with what), or "no check in this chunk".
- RULE: each branch that changes the outcome: `if <exact condition> -> <outcome>`, with the function that holds it. When a condition tests membership in a list, set, dict or enum group, copy every member verbatim; never write "certain types" or "some statuses".
- ORDER: what is saved or committed, and in which order relative to calls that can fail (for example "commits status PAID, then publishes; a failed publish leaves it PAID").
- ON ERROR: each try/except, suppress or error callback: what it catches and what happens - re-raised, retried (how often), recorded (where), only logged, sent to Sentry, or swallowed - and which later steps still run.
- CALLS OUT: each call to another service, queue, topic, email or table: the target as written, the credential or token it sends, and the payload shape.
- STATES: each status or field value it sets or skips on, verbatim.
- ABSENT: what the chunk plainly lacks where a reader would expect it: no permission check, no duplicate guard, no retry, a commented-out check - as what this chunk shows, never as a claim about the system.
For documentation or configuration, keep every decision, value and name a reader would look up, in the same spirit.

No word target: a chunk with one simple function needs three lines, a chunk with many branches needs all of them. Boilerplate, imports, licences and logging setup collapse to one short line or to nothing. Copy names, values and lists VERBATIM; never infer or add ones that are not literally there; never guess about spelling or intent. Never copy a password, token, key or a connection string that carries credentials; write <secret> in its place. Output only the notes.

{content}"""


# Round 8: what the trace showed the ledger still loses - the shape of what
# arrives and how it is parsed, the order of an entry's checks, loops that
# poll or retry, and the endpoint path a call goes to (written under a base
# URL variable, so the link to the route's owner was never made).
LEDGER2 = LEDGER.replace(
    "- ENTRY: each route",
    "- IN: what arrives and its exact shape - the fields read, the type or format checked (for example `event.type == 'order.created'`), conversions (camelCase to snake_case), and what happens to input that does not fit.\n- ENTRY: each route",
).replace(
    "or \"no check in this chunk\".",
    "or \"no check in this chunk\". When an entry runs several checks, give them in the order the code runs them, and what a request that stops at each one gets back.",
).replace(
    "- ORDER:",
    "- LOOP: each loop that polls, retries or waits: how many times, the wait, and what ends it.\n- ORDER:",
).replace(
    "the target as written,",
    "the target as written (for an HTTP call, the method and the path after the base URL variable, for example `GET /internal/orders/pending` with base `ORDERS_API_URL`),",
)


def condense(everything: bool = False, prompt: str = LEDGER, name: str = "ledger.json") -> None:
    conn = c.connect()
    sids = (
        exp.members(conn, exp.slice_leaves(conn))
        if everything
        else sl.slice_sections(conn)
    )
    done = exp.load(name)
    todo = [s for s in sids if str(s) not in done]
    items = [c.section(conn, s) for s in todo]

    def one(item: dict) -> tuple[str, dict]:
        got = exp.ask(prompt.replace("{content}", item["body"]), exp.HAIKU)
        return str(item["id"]), {
            "path": f"{item['source']}/{item['path']}",
            **got,
        }

    for sid, got in exp.run_pool(one, items):
        done[sid] = got
    exp.save(name, done)
    words = [len((v.get("text") or "").split()) for v in done.values()]
    print(
        "sections",
        len(done),
        "errors",
        sum("error" in v for v in done.values()),
        "words",
        round(sum(words) / len(words)),
        "cost",
        round(sum(v.get("cost") or 0 for v in done.values()), 2),
    )


def judge(run: str) -> None:
    conn = c.connect()
    notes_of = {int(k): v["text"] for k, v in exp.load("ledger.json").items()}
    secs: dict[str, list[int]] = {}
    for sid, source, path in conn.execute(
        "SELECT id, source, path FROM sections"
    ):
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
                f"--- {p} ---\n{notes_of.get(s, '')}"
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
            "arm": "notes-ledger",
            "verdicts": (got.get("structured") or {}).get("verdicts"),
            "cost": got.get("cost"),
        }

    rows = [
        r for r in exp.load(f"judged-{run}.json") if r["arm"] != "notes-ledger"
    ]
    rows += list(exp.run_pool(one, jobs, 8))
    exp.save(f"judged-{run}.json", rows)


if __name__ == "__main__":
    {
        "condense": condense,
        "condense-all": lambda: condense(True),
        "condense2": lambda: condense(False, LEDGER2, "ledger2.json"),
        "judge": lambda: judge(sys.argv[2]),
    }[sys.argv[1]]()
