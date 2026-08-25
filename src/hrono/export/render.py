"""Render the collapsed agent-facing tree (#078) to a path -> markdown mapping.

Per agent node: its stored brief text as-is (#059/#061 — already ends with its
Caution section; never regenerated), then a MECHANICAL child listing rendered
from the collapsed tree in code (titles + relative links, no LLM, no
hallucinated links). Leaf nodes list their sections; each section is rendered to
its own file, reassembled byte-identically from its stored passages (#032) with
an address header. Human notes render only when passed (M9 creates them; here
render-if-present). No file I/O — returns a deterministic path -> content map
that #081 materialises into a folder tree.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Mapping

from hrono.export.collapse import ExportTree
from hrono.ingest.store import get_content
from hrono.summarize import briefs


def render(
    conn: sqlite3.Connection,
    tree: ExportTree,
    *,
    notes: Mapping[int, str] | None = None,
) -> dict[str, str]:
    """Render ``tree`` to a {file path -> markdown content} mapping."""
    notes = notes or {}
    parent = {
        child: node.node_id
        for node in tree.nodes.values()
        for child in node.children
    }
    files: dict[str, str] = {}

    for node_id in sorted(tree.nodes):
        node = tree.nodes[node_id]
        directory = _directory(node_id, parent, conn)
        path = "root.md" if node_id == tree.root else f"{directory}/brief.md"
        files[path] = _node_markdown(conn, tree, node_id, notes.get(node_id))
        for section_id in node.sections:
            name = _section_name(conn, section_id)
            files[f"{directory}/{name}.md"] = _section_markdown(
                conn, section_id
            )
    return files


def _node_markdown(
    conn: sqlite3.Connection,
    tree: ExportTree,
    node_id: int,
    note: str | None,
) -> str:
    node = tree.nodes[node_id]
    parts = [_brief_text(conn, node_id).rstrip()]
    if node.children:
        parts.append("## Children\n")
        parts.append(
            "\n".join(
                f"- [{_heading(conn, child)}]({_name(conn, child)}/brief.md)"
                for child in node.children
            )
        )
    elif node.sections:
        parts.append("## Sections\n")
        parts.append(
            "\n".join(
                f"- [{_section_heading(conn, sid)}]"
                f"({_section_name(conn, sid)}.md)"
                for sid in node.sections
            )
        )
    if note:
        parts.append(f"## Notes\n\n{note}")
    return "\n\n".join(parts) + "\n"


def _section_markdown(conn: sqlite3.Connection, section_id: int) -> str:
    row = conn.execute(
        "SELECT path, uri FROM sections WHERE id = ?", (section_id,)
    ).fetchone()
    body = _reassemble(conn, section_id).decode("utf-8", "replace")
    return f"# {row['path']}\n\n<!-- {row['uri']} -->\n\n{body}"


def _reassemble(conn: sqlite3.Connection, section_id: int) -> bytes:
    rows = conn.execute(
        "SELECT content_hash FROM passages WHERE section_id = ? "
        "ORDER BY ordinal, id",
        (section_id,),
    ).fetchall()
    return b"".join(
        get_content(conn, row["content_hash"]) or b"" for row in rows
    )


def _directory(
    node_id: int, parent: Mapping[int, int], conn: sqlite3.Connection
) -> str:
    parts: list[str] = []
    cur = node_id
    while cur in parent:
        parts.append(_name(conn, cur))
        cur = parent[cur]
    return "/".join(reversed(parts))


def _brief_text(conn: sqlite3.Connection, node_id: int) -> str:
    row = briefs.get(conn, node_id)
    return row["text"] if row is not None else ""


def _heading(conn: sqlite3.Connection, node_id: int) -> str:
    lines = _brief_text(conn, node_id).strip().splitlines()
    first = lines[0].lstrip("#").strip() if lines else ""
    return first or f"node {node_id}"


def _name(conn: sqlite3.Connection, node_id: int) -> str:
    return _slug(_heading(conn, node_id)) or f"node-{node_id}"


def _section_heading(conn: sqlite3.Connection, section_id: int) -> str:
    row = conn.execute(
        "SELECT path FROM sections WHERE id = ?", (section_id,)
    ).fetchone()
    return row["path"] if row is not None else f"section {section_id}"


def _section_name(conn: sqlite3.Connection, section_id: int) -> str:
    return f"{_slug(_section_heading(conn, section_id))}-{section_id}"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]
