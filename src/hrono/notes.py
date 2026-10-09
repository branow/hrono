"""Human notes on a node or a section.

Append-only by design: the export shows a topic's notes to a traversing agent,
and an operator's later correction should sit ABOVE the earlier note rather
than erase it — the team may be acting on the one it replaces.

A note never pins. Annotating a topic is not correcting the map, and a comment
that silently froze a tree against every later update would be a trap for the
person who left it.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime

NODE = "node"
SECTION = "section"
KINDS = (NODE, SECTION)


def add(conn: sqlite3.Connection, kind: str, target_id: int, text: str) -> int:
    """Append a note; return its id."""
    if kind not in KINDS:
        raise ValueError(f"unknown note kind: {kind}")
    cursor = conn.execute(
        "INSERT INTO notes(kind, target_id, text, created_at) "
        "VALUES (?, ?, ?, ?)",
        (kind, target_id, text, _now()),
    )
    return int(cursor.lastrowid or 0)


def get(
    conn: sqlite3.Connection, kind: str, target_id: int
) -> tuple[tuple[int, str, str], ...]:
    """(id, text, created_at) for one entity, newest first."""
    rows = conn.execute(
        "SELECT id, text, created_at FROM notes "
        "WHERE kind = ? AND target_id = ? ORDER BY id DESC",
        (kind, target_id),
    ).fetchall()
    return tuple(
        (int(row["id"]), str(row["text"]), str(row["created_at"]))
        for row in rows
    )


def rendered(conn: sqlite3.Connection, kind: str = NODE) -> dict[int, str]:
    """target -> its notes as one block, newest first, for the export.

    One query for the whole tree: the renderer asks per node, and a query per
    node would put the cost of the feature on the corpus rather than on the
    notes.
    """
    collected: dict[int, list[str]] = {}
    for row in conn.execute(
        "SELECT target_id, text FROM notes WHERE kind = ? "
        "ORDER BY target_id, id DESC",
        (kind,),
    ).fetchall():
        collected.setdefault(int(row["target_id"]), []).append(str(row["text"]))
    return {
        target: _block(texts) for target, texts in collected.items() if texts
    }


def _block(texts: Sequence[str]) -> str:
    return "\n\n".join(text.strip() for text in texts)


def _now() -> str:
    return datetime.now(UTC).isoformat()
