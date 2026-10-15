# ruff: noqa: E501, SIM115, B007 - experiment harness; prompts read best whole
"""Round 8: a leaf brief writer that looks things up before it writes.

The trace showed the facts a hard question needs that no brief states are
mostly on the other side of a connection: who consumes the message a topic
publishes and what it does with it, what an endpoint a job calls really
selects (the brief guessed it from the endpoint's name), what repairs a
failed step. Name matching misses most of them, because the target is named
through a configuration key. Here the brief writer gets two tools over the
condensations of every section of the tree - `search` (full text) and `read`
(one section) - and is told to find the other side of each connection before
it writes.

Usage: uv run --with claude-agent-sdk python investigate.py index
       uv run --with claude-agent-sdk python investigate.py brief <leaf,...|questions>
       uv run python investigate.py export
"""

from __future__ import annotations

import asyncio
import re
import shutil
import sqlite3
import sys

import agent_v2
import exp
from exp import c, sl

INDEX = exp.DATA / "condensations.db"  # local, not committed
OUT = "briefs-I.json"
EXPORT = exp.Path.home() / "hrono-eval" / "export-bcreg-v3i-L3"

INVESTIGATE = """You write the brief of one topic of a larger system. Below are the condensations of the topic's sections, each under its source's name, then condensations of sections in other topics that share names with it. A reader (human or AI agent) gets only this brief - condensations are not shown anywhere - so everything a reader needs to answer exact questions about this topic, and about how it connects to the rest of the system, must be in it.

Before writing, investigate with two tools over the condensations of every section in the whole system: `search` (full-text search; returns section ids, source paths and the topic each belongs to) and `read` (one section's condensation by id). Find:
- The other side of each message, queue, event, endpoint, call, table or file this topic sends to or receives from: who receives what it sends and what the receiver does with it (its checks, what it saves, what happens when it fails), and who sends what it receives and when. When the target is named through a configuration key or variable, look that key up to find the real name it holds, then search for that name.
- Behaviour this topic relies on that lives elsewhere: what an endpoint it calls actually selects or returns, what a shared function or record does. Never describe it from its name.
- What retries, repairs or re-drives this topic's work when one of its steps fails, or that nothing does.
Use at most 15 lookups and stop when the connections are clear.

Then write, in this order:
1. One or two sentences: what this topic does and what it hands work to or takes work from.
2. Contract: what reaches it and from where, what it sends or writes and to where, with the exact shape of what crosses the boundary.
3. Entry points: for each route, handler, listener, job or public function, the checks that guard it in the order they run, each with its exact condition, or that none is shown.
4. Decisions: every branch that changes an outcome, one line each - the exact condition, the outcome, and the function that holds it. Copy every member of a list, set or group verbatim. Include every state a record moves to.
5. Order and failure: what is saved or committed before a step that can fail; for each error handler what it catches and what happens (re-raised, retried and how often, recorded where, only logged, sent to Sentry, swallowed) and which later steps still run; each loop that polls or retries.
6. Connections: one line per counterpart you found or were given - the other topic by its title and the source path, what crosses and in which direction, what the other side does with it (its checks, the state it sets, its failure handling), and the conclusion the two sides support together (for example a case one side sends that the other drops, or a failure nothing repairs).
7. Hazards: where work can be lost, duplicated, corrupted or let through unchecked - as the code shows it. Nothing about health checks, configuration validation, logging or typing.
8. The sources to open first, and what each holds.

Every statement about another topic comes from a condensation you read or were given, with its source path; if you could not find the other side, say so. Every check comes with its condition. Keep names, values and lists verbatim. No word target: one line per fact, no padding, no repetition. Leave out startup and wiring, packaging, build and deployment files, logging setup, licences and test plumbing, unless the question of what this topic does depends on them. Never describe the text you were given ("these condensations"); write about the topic. Output only the brief in markdown: no notes about tools or your process.

{content}"""


def index() -> None:
    """An FTS5 table over the stored condensation of every section, with its
    path and leaf topic, so the brief writer can search the whole tree."""
    conn = c.connect()
    leaf = exp.leaf_map(conn)
    title = sl.titles(conn)
    if INDEX.exists():
        INDEX.unlink()
    db = sqlite3.connect(INDEX)
    db.execute(
        "CREATE VIRTUAL TABLE docs USING fts5(path, text, section UNINDEXED, "
        "topic UNINDEXED, tokenize='porter unicode61 remove_diacritics 2')"
    )
    rows = conn.execute(
        "SELECT s.id, s.source || '/' || s.path, d.text FROM sections s JOIN condensations d "
        "ON d.content_hash = s.content_hash AND d.model_name = 'condense-contracts'"
    ).fetchall()
    db.executemany(
        "INSERT INTO docs VALUES (?, ?, ?, ?)",
        [
            (p, t, sid, title.get(leaf.get(sid), "?"))
            for sid, p, t in rows
            if not exp.is_test(p)
        ],
    )
    db.commit()
    print("indexed", db.execute("SELECT count(*) FROM docs").fetchone()[0])


def notes_of(conn) -> callable:
    ledger2 = exp.load("ledger2.json")
    ledger = exp.load("ledger.json")

    def notes(sid: int) -> str:
        got = ledger2.get(str(sid)) or ledger.get(str(sid))
        return got["text"] if got else exp.stored_condensation(conn, sid)

    return notes


def search(query: str) -> str:
    db = sqlite3.connect(f"file:{INDEX}?mode=ro", uri=True)
    terms = [t for t in re.findall(r"[\w]+", query) if len(t) > 1]
    if not terms:
        return "no terms"
    fts = " OR ".join(f'"{t}"' for t in terms)
    rows = db.execute(
        "SELECT section, path, topic, snippet(docs, 1, '[', ']', ' … ', 24) "
        "FROM docs WHERE docs MATCH ? ORDER BY bm25(docs, 2.0, 1.0) LIMIT 10",
        (fts,),
    ).fetchall()
    return (
        "\n".join(
            f"section {s} | {p} | topic: {t}\n  {snip}"
            for s, p, t, snip in rows
        )
        or "no match"
    )


def read(sid: int) -> str:
    db = sqlite3.connect(f"file:{INDEX}?mode=ro", uri=True)
    row = db.execute(
        "SELECT path, topic, text FROM docs WHERE section = ?", (sid,)
    ).fetchone()
    return f"{row[0]} (topic: {row[1]})\n{row[2]}" if row else "no such section"


async def _write(prompt: str) -> dict:
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        ResultMessage,
        create_sdk_mcp_server,
        query,
        tool,
    )

    calls = []

    @tool(
        "search",
        "Full-text search over the condensations of every section in the system. Returns up to 10 hits: section id, source path, topic, matching snippet.",
        {"query": str},
    )
    async def _search(args):
        calls.append(("search", args["query"]))
        return {"content": [{"type": "text", "text": search(args["query"])}]}

    @tool(
        "read",
        "The condensation of one section, by section id.",
        {"section": int},
    )
    async def _read(args):
        calls.append(("read", args["section"]))
        return {
            "content": [{"type": "text", "text": read(int(args["section"]))}]
        }

    server = create_sdk_mcp_server(
        name="tree", version="1.0", tools=[_search, _read]
    )
    options = ClaudeAgentOptions(
        model=exp.SONNET,
        system_prompt="You write briefs of parts of a software system for a knowledge base.",
        tools=[],
        mcp_servers={"tree": server},
        allowed_tools=["mcp__tree__search", "mcp__tree__read"],
        max_turns=24,
        setting_sources=[],
        extra_args={"safe-mode": None},  # no MCP servers or their notes
        cwd=str(c.WORKDIR),
        cli_path=shutil.which("claude"),
        thinking={"type": "disabled"},
    )
    result = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message
    return {
        "text": clean(result.result or ""),
        "cost": result.total_cost_usd,
        "calls": calls,
    }


def clean(text: str) -> str:
    """Drop a note the CLI's environment sometimes leaks into the answer."""
    return re.sub(r"^Note: the claude\.ai[^\n]*\n+", "", text.strip()).strip()


def question_leaves(conn) -> list[int]:
    leaf = exp.leaf_map(conn)
    secs: dict[str, list[int]] = {}
    for sid, source, path in conn.execute(
        "SELECT id, source, path FROM sections"
    ):
        secs.setdefault(f"{source}/{path}", []).append(sid)
    qs = [
        q
        for q in sl.questions()
        if q["qid"] in ("hard-legacy-0", "hard-failure-1")
    ]
    return sorted(
        {
            leaf[s]
            for q in qs
            for f in q["facts"]
            for p in f["files"]
            for s in secs.get(p, [])
            if s in leaf
        }
    )


def brief(which: str) -> None:
    sys.path.insert(0, str(exp.HERE.parents[3] / "src"))
    from hrono.summarize.briefs import labeled

    conn = c.connect()
    links = exp.load("links.json")
    condensed = exp.all_condensed()
    title = sl.titles(conn)
    nodes = (
        question_leaves(conn)
        if which == "questions"
        else [int(x) for x in which.split(",")]
    )
    out = exp.load(OUT)

    def one(node: int):
        conn2 = c.connect()
        notes = notes_of(conn2)
        rows = conn2.execute(
            "SELECT s.id, s.path FROM node_members m JOIN sections s ON s.id = m.section_id "
            "WHERE m.node_id = ? ORDER BY s.uri, s.id",
            (node,),
        ).fetchall()
        content = labeled([(path, notes(sid)) for sid, path in rows])
        block = exp.linked_block(node, links, condensed, title, conn2, notes)
        if block:
            content += (
                "\n\n=== CONDENSATIONS FROM OTHER TOPICS THAT SHARE NAMES ===\n"
                + block
            )
        for attempt in range(3):
            try:
                return str(node), asyncio.run(
                    _write(INVESTIGATE.replace("{content}", content))
                )
            except Exception as exc:  # noqa: BLE001
                err = str(exc)
        return str(node), {"error": err, "cost": 0}

    todo = [n for n in nodes if str(n) not in out or "error" in out[str(n)]]
    print("leaves", len(nodes), "to write", len(todo))
    for node, got in exp.run_pool(one, todo, 4):
        out[node] = got
        exp.save(OUT, out)
        print(
            node,
            len((got.get("text") or "").split()),
            "words",
            len(got.get("calls") or []),
            "lookups",
            round(got.get("cost") or 0, 2),
        )
    print("cost", round(sum(v.get("cost") or 0 for v in out.values()), 2))


def export() -> None:
    """v3w (W briefs plus linked topics) with these briefs in place."""
    if EXPORT.exists():
        shutil.rmtree(EXPORT)
    shutil.copytree(agent_v2.EXPORT, EXPORT)
    got = exp.load(OUT)
    n = 0
    for brief_md in EXPORT.rglob("brief.md"):
        tail = brief_md.parent.name.rsplit("-", 1)[-1]
        if tail in got and got[tail].get("text"):
            old = brief_md.read_text()
            keep = re.search(r"\n## Sources\n.*", old, re.S)
            head = old.splitlines()[0]
            body = got[tail]["text"]
            if body.startswith("# "):
                body = body.split("\n", 1)[1]
            brief_md.write_text(
                head
                + "\n\n"
                + body.strip()
                + "\n"
                + (keep.group(0) if keep else "")
            )
            n += 1
    print("replaced", n, "export", EXPORT)


if __name__ == "__main__":
    {"index": index, "brief": lambda: brief(sys.argv[2]), "export": export}[
        sys.argv[1]
    ]()
