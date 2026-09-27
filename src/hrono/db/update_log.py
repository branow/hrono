"""The shared ``update_log`` audit trail: one row per lifecycle decision.

Introduced by the propagate cascade (#087) and written by the incubator too
(#095), so the single writer lives here rather than being re-implemented per
domain: the dashboard reads one table with one shape whatever produced the row.
``verdict`` says what was decided, ``action`` what was done with it, and
``climbed_to`` is the cascade's stop node (null for anything that does not
climb).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


def record(
    conn: sqlite3.Connection,
    tree: str,
    node_id: int,
    verdict: str,
    action: str,
    climbed_to: int | None = None,
) -> None:
    """Append one audit row for a node-level update decision."""
    conn.execute(
        "INSERT INTO update_log(tree, node_id, verdict, action, climbed_to, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            tree,
            node_id,
            verdict,
            action,
            climbed_to,
            datetime.now(UTC).isoformat(),
        ),
    )


# A log view that renders forty thousand rows is one nobody opens twice.
PAGE = 100


def recent(
    conn: sqlite3.Connection, tree: str, limit: int = PAGE
) -> tuple[tuple[sqlite3.Row, ...], int]:
    """The newest decisions for a tree, and how many older ones there are.

    The count matters as much as the rows: "showing 100 of 100" and "showing
    100 of 41,000" are different situations, and a page that shows only the
    first cannot tell them apart.
    """
    rows = conn.execute(
        "SELECT id, node_id, verdict, action, climbed_to, created_at "
        "FROM update_log WHERE tree = ? ORDER BY id DESC LIMIT ?",
        (tree, limit),
    ).fetchall()
    total = int(
        conn.execute(
            "SELECT COUNT(*) FROM update_log WHERE tree = ?", (tree,)
        ).fetchone()[0]
    )
    return tuple(rows), total
