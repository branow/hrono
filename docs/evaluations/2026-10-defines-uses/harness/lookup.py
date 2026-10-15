# ruff: noqa: E501 - experiment harness; prompts read best whole
"""Round 9, step 1: can a brief writer that looks things up say which looked-up
files it actually used?

A lookup into another branch is a dependency the tree does not know about:
when that file changes, incremental update would not touch the brief. The plan
is to store only the lookups that shaped the brief, as relations an update
follows. That is worth building only if the writer's `Used` list is reliable,
which this step checks by hand on three topics.

What the writer sees is what exists when a leaf brief is written in a real
build (condense runs over every section before any brief): virtual files
`source/<repo>/<path>` (the raw text) and `condensed/<repo>/<path>.md` (the
stored condensations of that file), behind tools shaped like Claude Code's
`Grep`, `Read` and `Glob`. No briefs. Its own topic's condensations come from
the new seeded condense prompt; the brief prompt is the new seeded one plus
the lookup instructions.

Usage: uv run --with claude-agent-sdk python lookup.py brief 523,694,797
"""

from __future__ import annotations

import asyncio
import fnmatch
import re
import shutil
import sys

import exp
from exp import c

sys.path.insert(0, str(exp.HERE.parents[3] / "src"))
from hrono.registry.collections.prompts import _BRIEF, _CONDENSE  # noqa: E402
from hrono.summarize.briefs import labeled  # noqa: E402

OUT = "briefs-L.json"
MAX_OUT = 12_000  # characters a tool answer may return

LOOKUP = """

Before writing, look up what this topic connects to. You have read-only tools over the files of the whole system: `source/<repo>/<path>` is the text of each source file and `condensed/<repo>/<path>.md` its condensation. Use `Grep` (a regular expression, optionally limited to a path glob) and `Glob` to find files, and `Read` to read one. Find the other side of each message, queue, event, endpoint, call, table or file this topic sends to or receives from - who receives what it sends and what it does with it, who sends what it receives - and what an endpoint or function it calls really does. When a target is named through a configuration key, look the key up to find the name it holds, then search for that name. This topic's own files are already given above, under their paths: spend the lookups on the other parts. Work in order: first list every connection the topic's files show (each message, queue, endpoint, call, table or configuration key that names another part); then, for each, find the file on the other side with `Grep` and read what it does there. Mark something "(behaviour not in this topic)" only after you looked for it and did not find it. Use at most 15 tool calls.

After the brief, add a final section `## Used`: one line for each looked-up file that a statement in the brief comes from - `- <path>: <the statement>`, with the path exactly as the tools print it (starting `source/` or `condensed/`) - and nothing for files you opened but did not use, nor for this topic's own files. A statement about another part must come from a file listed there."""


def files(conn) -> dict[str, str]:
    """Every virtual file: raw source and stored condensation per path."""
    src: dict[str, list[str]] = {}
    con: dict[str, list[str]] = {}
    for source, path, body, cond in conn.execute(
        "SELECT s.source, s.path, ct.body, d.text FROM sections s "
        "JOIN contents ct USING (content_hash) LEFT JOIN condensations d "
        "ON d.content_hash = s.content_hash AND d.model_name = 'condense-contracts' "
        "ORDER BY s.source, s.path, s.ordinal"
    ):
        key = f"{source}/{path}"
        src.setdefault(key, []).append(
            body.decode() if isinstance(body, bytes) else body
        )
        if cond:
            con.setdefault(key, []).append(cond)
    out = {f"source/{k}": "\n".join(v) for k, v in src.items()}
    out.update({f"condensed/{k}.md": "\n\n".join(v) for k, v in con.items()})
    return out


FILES: dict[str, str] = {}
NONE = ""  # set in brief(): how paths begin, said when a lookup finds nothing


def glob(pattern: str) -> str:
    hits = [
        p
        for p in FILES
        if fnmatch.fnmatch(p, pattern)
        or fnmatch.fnmatch(p, pattern.rstrip("/") + "/**")
    ]
    return "\n".join(sorted(hits)[:200]) or NONE


def grep(
    pattern: str,
    path: str = "",
    mode: str = "files",
    ignore_case: bool = False,
    context: int = 0,
) -> str:
    try:
        rx = re.compile(pattern, re.I if ignore_case else 0)
    except re.error as exc:
        return f"bad pattern: {exc}"
    out: list[str] = []
    for p in sorted(FILES):
        if path and not (
            fnmatch.fnmatch(p, path) or p.startswith(path.rstrip("*"))
        ):
            continue
        lines = FILES[p].splitlines()
        hit = [i for i, line in enumerate(lines) if rx.search(line)]
        if not hit:
            continue
        if mode == "files":
            out.append(p)
        else:
            for i in hit[:20]:
                lo, hi = max(0, i - context), min(len(lines), i + context + 1)
                out.extend(f"{p}:{j + 1}: {lines[j]}" for j in range(lo, hi))
        if sum(len(x) for x in out) > MAX_OUT:
            out.append("... (more; narrow the pattern or path)")
            break
    return "\n".join(out)[:MAX_OUT] or "no match. " + NONE


def read(path: str, offset: int = 0, limit: int = 400) -> str:
    text = FILES.get(path)
    if text is None:
        return "no such file. " + NONE
    lines = text.splitlines()[offset : offset + limit]
    body = "\n".join(f"{offset + i + 1}\t{x}" for i, x in enumerate(lines))
    return body[:MAX_OUT]


async def _write(prompt: str) -> dict:
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        ResultMessage,
        create_sdk_mcp_server,
        query,
        tool,
    )

    calls: list[tuple] = []

    def answer(text: str) -> dict:
        return {"content": [{"type": "text", "text": text}]}

    @tool(
        "Grep",
        "Search file contents with a regular expression. `path`: optional path glob (for example `source/lear/queue_services/**`). `mode`: `files` (matching paths, the default) or `content` (matching lines with path and line number). `context`: lines around each match. `ignore_case`: bool.",
        {
            "pattern": str,
            "path": str,
            "mode": str,
            "context": int,
            "ignore_case": bool,
        },
    )
    async def _grep(args):
        calls.append(("Grep", args.get("pattern"), args.get("path", "")))
        return answer(
            grep(
                args["pattern"],
                args.get("path", ""),
                args.get("mode", "files"),
                bool(args.get("ignore_case")),
                int(args.get("context") or 0),
            )
        )

    @tool(
        "Glob",
        "List file paths matching a glob, for example `source/sbc-pay/**/config.py`.",
        {"pattern": str},
    )
    async def _glob(args):
        calls.append(("Glob", args["pattern"]))
        return answer(glob(args["pattern"]))

    @tool(
        "Read",
        "Read a file by path, with numbered lines. `offset`: first line (0-based), `limit`: lines.",
        {"path": str, "offset": int, "limit": int},
    )
    async def _read(args):
        calls.append(("Read", args["path"]))
        return answer(
            read(
                args["path"],
                int(args.get("offset") or 0),
                int(args.get("limit") or 400),
            )
        )

    server = create_sdk_mcp_server(
        name="files", version="1.0", tools=[_grep, _glob, _read]
    )
    options = ClaudeAgentOptions(
        model=exp.SONNET,
        system_prompt="You write briefs of parts of a software system for a knowledge base.",
        tools=[],
        mcp_servers={"files": server},
        allowed_tools=[
            "mcp__files__Grep",
            "mcp__files__Glob",
            "mcp__files__Read",
        ],
        max_turns=24,
        setting_sources=[],
        cwd=str(c.WORKDIR),
        cli_path=shutil.which("claude"),
        thinking={"type": "disabled"},
    )
    result = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message
    text = re.sub(
        r"^Note: the claude\.ai[^\n]*\n+", "", (result.result or "").strip()
    )
    text = re.sub(r"\n[^\n]*MCP servers? claude\.ai[^\n]*\n", "\n", text)
    return {"text": text, "cost": result.total_cost_usd, "calls": calls}


def used(text: str) -> list[tuple[str, str]]:
    part = text.split("## Used", 1)
    if len(part) < 2:
        return []
    return [
        (m.group(1).strip("` "), m.group(2).strip())
        for m in re.finditer(r"^- `?([^`:\s]+)`?:\s*(.+)$", part[1], re.M)
    ]


def brief(nodes: list[int]) -> None:
    global FILES
    conn = c.connect()
    FILES = files(conn)
    global NONE
    repos = sorted({p.split("/")[1] for p in FILES})
    NONE = (
        "Paths begin source/<repo>/ or condensed/<repo>/, with repos: "
        + ", ".join(repos)
    )
    out = exp.load(OUT)
    for node in nodes:
        rows = conn.execute(
            "SELECT s.id, 'source/' || s.source || '/' || s.path FROM node_members m JOIN sections s ON s.id = m.section_id "
            "WHERE m.node_id = ? ORDER BY s.uri, s.id",
            (node,),
        ).fetchall()
        items = [c.section(conn, sid) for sid, _ in rows]
        cond = dict(
            exp.run_pool(
                lambda it: (
                    it["id"],
                    exp.ask(
                        _CONDENSE.replace("{content}", it["body"]), exp.HAIKU
                    ),
                ),
                items,
                6,
            )
        )
        content = labeled([(p, cond[sid].get("text") or "") for sid, p in rows])
        got = asyncio.run(
            _write(
                _BRIEF.replace("{content}", content).replace(
                    "Output only the description in markdown, nothing else.",
                    "Output only the description in markdown, then the Used section."
                    + LOOKUP,
                )
            )
        )
        got["condense_cost"] = sum(v.get("cost") or 0 for v in cond.values())
        own = {p for _, p in rows} | {
            "condensed/" + p[len("source/") :] + ".md" for _, p in rows
        }
        got["used"] = [u for u in used(got["text"]) if u[0] not in own]
        got["own_declared"] = [u[0] for u in used(got["text"]) if u[0] in own]
        out[str(node)] = got
        exp.save(OUT, out)
        print(
            node,
            "calls",
            len(got["calls"]),
            "used",
            len(got["used"]),
            "words",
            len(got["text"].split()),
            "cost",
            round(got["cost"] + got["condense_cost"], 2),
        )


if __name__ == "__main__":
    brief([int(x) for x in sys.argv[2].split(",")])
