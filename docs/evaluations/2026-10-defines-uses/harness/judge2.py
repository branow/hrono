# ruff: noqa: E501 - experiment harness
"""A stricter judge: one claim per call, thinking on, the quote required
before the verdict. The batched judge answered "no" with an empty quote on
claims the notes state word for word."""

from __future__ import annotations

import asyncio
import shutil
import sys

import exp
from exp import c, sl

ONE = """Below is a text about a software system, then a claim. Does the text state the claim?

TEXT:
{pages}

CLAIM: {claim}

First search the whole text for the passage that states it (names may differ slightly; a list that leaves an item out states that the item is not there). Then answer: "stated": true if the text states the claim, false if it does not, states only part of it, or contradicts it. "quote": the words that state it, or "" if none."""

SCHEMA = {
    "type": "object",
    "properties": {"quote": {"type": "string"}, "stated": {"type": "boolean"}},
    "required": ["quote", "stated"],
}


async def _ask(prompt: str) -> dict:
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    options = ClaudeAgentOptions(
        model=exp.SONNET,
        system_prompt=c.SYSTEM,
        tools=[],
        max_turns=3,
        setting_sources=[],
        cwd=str(c.WORKDIR),
        cli_path=shutil.which("claude"),
        thinking={"type": "enabled", "budget_tokens": 4000},
        output_format={"type": "json_schema", "schema": SCHEMA},
    )
    result = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message
    return {**(result.structured_output or {}), "cost": result.total_cost_usd}


def ask(prompt: str) -> dict:
    for attempt in range(3):
        try:
            return asyncio.run(_ask(prompt))
        except Exception as exc:  # noqa: BLE001
            if attempt == 2:
                return {"error": str(exc), "cost": 0}
    return {}


def pages_by_arm(conn) -> dict[str, dict[tuple[str, int], str]]:
    """Each arm's text per (question, fact), as the batched judge saw it."""
    leaf = exp.leaf_map(conn)
    parent = dict(conn.execute("SELECT child_id, parent_id FROM node_children"))
    secs: dict[str, list[int]] = {}
    for sid, source, path in conn.execute("SELECT id, source, path FROM sections"):
        secs.setdefault(f"{source}/{path}", []).append(sid)
    arms = exp.arm_pages(conn)
    ledger = {int(k): v["text"] for k, v in exp.load("ledger.json").items()}
    out: dict[str, dict] = {}
    for q in sl.questions():
        for i, fact in enumerate(q["facts"]):
            leaves = sorted(
                {leaf[s] for p in fact["files"] for s in secs.get(p, []) if s in leaf}
            )
            nodes = leaves + sorted({parent[n] for n in leaves if n in parent})
            for arm, texts in arms.items():
                out.setdefault(arm, {})[(q["qid"], i)] = "\n\n".join(
                    f"--- page ---\n{texts.get(n, '')}" for n in nodes
                )
            out.setdefault("notes-v3", {})[(q["qid"], i)] = "\n\n".join(
                f"--- {p} ---\n{exp.stored_condensation(conn, s)}"
                for p in fact["files"]
                for s in secs.get(p, [])
            )
            out.setdefault("notes-ledger", {})[(q["qid"], i)] = "\n\n".join(
                f"--- {p} ---\n{ledger.get(s, '')}"
                for p in fact["files"]
                for s in secs.get(p, [])
            )
    return out


def run(arms: list[str], name: str, only: list[tuple[str, int]] | None = None) -> None:
    conn = c.connect()
    pages = pages_by_arm(conn)
    split = exp.load("claims.json")
    jobs = []
    for qid, got in split.items():
        for f in got["structured"]["facts"]:
            if only and (qid, f["fact"]) not in only:
                continue
            for i, cl in enumerate(f["claims"]):
                for arm in arms:
                    jobs.append((qid, f["fact"], i, arm, cl["claim"]))
    done = {(r["qid"], r["fact"], r["claim"], r["arm"]): r for r in exp.load(name) or []}
    todo = [j for j in jobs if (j[0], j[1], j[2], j[3]) not in done]

    def one(job):
        qid, fact, i, arm, claim = job
        got = ask(ONE.format(claim=claim, pages=pages[arm][(qid, fact)]))
        return {"qid": qid, "fact": fact, "claim": i, "arm": arm, **got}

    rows = list(done.values())
    for n, row in enumerate(exp.run_pool(one, todo, 8), 1):
        rows.append(row)
        if n % 25 == 0:
            exp.save(name, rows)
    exp.save(name, rows)
    print(name, len(rows), "errors", sum("error" in r for r in rows),
          "cost", round(sum(r.get("cost") or 0 for r in rows), 2))


def report(name: str) -> None:
    split = exp.load("claims.json")
    kind = {(q, f["fact"], i): cl["kind"] for q, g in split.items()
            for f in g["structured"]["facts"] for i, cl in enumerate(f["claims"])}
    table: dict[str, dict[str, list[int]]] = {}
    for r in exp.load(name):
        cell = table.setdefault(r["arm"], {}).setdefault(kind[(r["qid"], r["fact"], r["claim"])], [0, 0])
        cell[0] += bool(r.get("stated"))
        cell[1] += 1
    for arm, cells in sorted(table.items()):
        print(arm, {k: f"{y}/{n}" for k, (y, n) in sorted(cells.items())})


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "pilot":
        run(["notes-ledger", "A-v3"], "judge2-pilot.json",
            [("hard-inconsistency-1", 1), ("hard-inconsistency-1", 5)])
        report("judge2-pilot.json")
    elif cmd == "run":
        run(sys.argv[3].split(","), f"judge2-{sys.argv[2]}.json")
        report(f"judge2-{sys.argv[2]}.json")
    else:
        report(f"judge2-{sys.argv[2]}.json")
