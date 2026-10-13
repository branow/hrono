# ruff: noqa: E501 - experiment harness; prompts read best whole
"""Round 2: references that cross the content's edge, matched by name first.

Round 1 (condense_links.py) got mostly the chunk's own imports and helpers,
and embedding a reference ranked look-alike pages as high as the right one.
Here the request names what NOT to list and asks for the most specific name
the content gives (URL, path, topic, config key, title). Matching tries that
name in the full-text index of the other pages first; the description
embedded is the fallback. Calls go through the Agent SDK with thinking off.

Usage: uv run --with claude-agent-sdk python links2.py call
       uv run python links2.py link
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import condense_links as c  # noqa: E402

OUT = c.OUT.parent / "pilot2.json"
MODEL = "claude-haiku-4-5-20251001"
LINKS = (
    "\n\nAlso list REFERENCES: only what lies OUTSIDE this content and takes "
    "part in its job - another service or API it calls or is called by, a "
    "queue or topic, a scheduled job, a database or store another part owns, "
    "an external system, another document or page it points to, a team or "
    "role it hands work to. Do NOT list this content's own functions, "
    "imported libraries, frameworks, types, enums, models, constants, "
    "logging or error tracking. For each give `target`: the most specific "
    "name the content itself gives (a URL or endpoint path, a topic or queue "
    "name, a config key, a document title, a function defined elsewhere), "
    "verbatim; `direction`: sends, receives or depends; and `what`: one "
    "sentence on what passes and any condition the content attaches (who "
    "may, which credential is sent, what is or is not checked). An empty "
    "list is right when nothing crosses the edge."
)
SCHEMA = {
    "type": "object",
    "properties": {
        "condensed": {"type": "string"},
        "references": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "target": {"type": "string"},
                    "direction": {"enum": ["sends", "receives", "depends"]},
                    "what": {"type": "string"},
                },
                "required": ["target", "direction", "what"],
            },
        },
    },
    "required": ["condensed", "references"],
}


async def _ask(prompt: str) -> dict:
    from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, query

    options = ClaudeAgentOptions(
        model=MODEL,
        system_prompt=c.SYSTEM,
        tools=[],
        max_turns=3,
        setting_sources=[],
        cwd=str(c.WORKDIR),
        cli_path=shutil.which("claude"),
        thinking={"type": "disabled"},
        output_format={"type": "json_schema", "schema": SCHEMA},
    )
    result = None
    async for message in query(prompt=prompt, options=options):
        if isinstance(message, ResultMessage):
            result = message
    return {
        "structured": result.structured_output,
        "cost": result.total_cost_usd,
        "seconds": result.duration_ms / 1000,
        "usage": result.model_usage,
    }


def run_calls() -> None:
    conn = c.connect()
    tpl = c.template(conn)
    items = [c.section(conn, sid) for sid in c.SECTIONS]
    c.WORKDIR.mkdir(parents=True, exist_ok=True)

    def one(item: dict) -> dict:
        prompt = tpl.replace("{content}", item["body"]) + LINKS
        got = asyncio.run(_ask(prompt))
        return {**{k: item[k] for k in ("id", "source", "path")}, **got}

    with ThreadPoolExecutor(5) as pool:
        out = list(pool.map(one, items))
    OUT.write_text(json.dumps(out, indent=1))
    print("cost", round(sum(o["cost"] or 0 for o in out), 3))
    print("seconds", [round(o["seconds"]) for o in out])


NAME = re.compile(r"[A-Za-z][\w./-]*[\w]")


def names(text: str) -> list[str]:
    """The identifier-like names in a text: snake_case, camelCase, dotted,
    paths. Plain words ("template", "repository") are left out: they match
    everywhere and say nothing about which page is meant."""
    found = [
        n
        for n in NAME.findall(text)
        if "_" in n
        or "/" in n
        or "." in n.strip(".")
        or re.search(r"[a-z][A-Z]", n)
    ]
    return sorted(set(found), key=len, reverse=True)


def phrase(name: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", name)
    return '"' + " ".join(words) + '"' if words else ""


def run_links() -> None:
    from sentence_transformers import SentenceTransformer

    conn = c.connect()
    rows = conn.execute(
        "SELECT p.id, p.path, p.source_type, p.source, p.section_id, e.vector "
        "FROM passages p JOIN embeddings e ON e.content_hash = p.content_hash"
    ).fetchall()
    level = dict(conn.execute("SELECT id, level FROM nodes"))
    leaf_of_section = dict(
        conn.execute(
            "SELECT m.section_id, MIN(m.node_id) FROM node_members m "
            "JOIN nodes n ON n.id = m.node_id WHERE n.level = 0 GROUP BY 1"
        )
    )
    title = {
        n: (t or "?").strip().splitlines()[0].lstrip("# ")
        for n, t in conn.execute("SELECT node_id, text FROM briefs")
    }
    page_of: dict[int, int | None] = {}
    for pid, path, kind, source, sid, _ in rows:
        if kind == "node":
            node = int(source.removeprefix("node-"))
            page_of[pid] = node if level.get(node) == 0 else None
        elif c.TEST.search(path or ""):
            page_of[pid] = None
        else:
            page_of[pid] = leaf_of_section.get(sid)
    ids = [r[0] for r in rows]
    keep = np.array([page_of[i] is not None for i in ids])
    m = np.stack([np.frombuffer(r[5], dtype=np.float32) for r in rows])
    m = m / np.linalg.norm(m, axis=1, keepdims=True)
    model = SentenceTransformer(c.EMBED)

    def by_name(text: str, own: int | None) -> tuple[str, list[int]]:
        """Pages ranked by the names of the reference they hold: each name
        votes 1/(pages holding it), so a rare name outweighs a common one."""
        score: dict[int, float] = {}
        used: list[str] = []
        for name in names(text):
            q = phrase(name)
            if not q:
                continue
            hits = conn.execute(
                "SELECT passage_id FROM passages_fts WHERE passages_fts MATCH ? LIMIT 2000",
                (q,),
            ).fetchall()
            pages = {page_of.get(pid) for (pid,) in hits} - {None, own}
            if not pages or len(pages) > 40:
                continue
            used.append(name)
            for page in pages:
                score[page] = score.get(page, 0.0) + 1.0 / len(pages)
        best = sorted(score, key=lambda p: -score[p])[:3]
        return ", ".join(used[:4]), best

    def by_meaning(text: str, own: int | None) -> list[int]:
        q = model.encode([text])[0]
        scores = np.where(keep, m @ (q / np.linalg.norm(q)), -1.0)
        pages: list[int] = []
        for i in np.argsort(-scores):
            page = page_of[ids[i]]
            if page != own and page not in pages:
                pages.append(page)
            if len(pages) == 3:
                break
        return pages

    for item in json.loads(OUT.read_text()):
        own = leaf_of_section.get(item["id"])
        refs = (item["structured"] or {}).get("references", [])
        print(
            f"\n## {item['source']}/{item['path']} (own page {own}: {title.get(own)})"
        )
        for ref in refs:
            name, pages = by_name(f"{ref['target']} {ref['what']}", own)
            how = f"name `{name}`" if pages else "meaning"
            if not pages:
                pages = by_meaning(f"{ref['target']}: {ref['what']}", own)
            shown = "; ".join(f"{p} {title.get(p, '?')[:55]}" for p in pages)
            print(
                f"- [{ref['direction']}] {ref['target']} -- {ref['what']}\n    -> by {how}: {shown}"
            )


if __name__ == "__main__":
    {"call": run_calls, "link": run_links}[sys.argv[1]]()
