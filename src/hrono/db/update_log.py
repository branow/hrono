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
    conn: sqlite3.Connection,
    tree: str,
    limit: int = PAGE,
    offset: int = 0,
    verdict: str = "",
    action: str = "",
    node_id: int = 0,
) -> tuple[tuple[sqlite3.Row, ...], int]:
    """One page of a tree's decisions, newest first, and how many match.

    The count matters as much as the rows: "showing 100 of 100" and "showing
    100 of 41,000" are different situations, and a page that shows only the
    first cannot tell them apart. Filter and page are SQL, so a log of forty
    thousand rows costs one page to read, not the log.
    """
    where = "tree = ?"
    args: list[object] = [tree]
    for column, value in (
        ("verdict", verdict),
        ("action", action),
        ("node_id", node_id),
    ):
        if value:
            where += f" AND {column} = ?"
            args.append(value)
    rows = conn.execute(
        "SELECT id, node_id, verdict, action, climbed_to, created_at "
        f"FROM update_log WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        (*args, limit, offset),
    ).fetchall()
    total = int(
        conn.execute(
            f"SELECT COUNT(*) FROM update_log WHERE {where}", args
        ).fetchone()[0]
    )
    return tuple(rows), total


def kinds(
    conn: sqlite3.Connection, tree: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The verdicts and actions a tree's log holds, for the filter's choices."""
    found = [
        tuple(
            str(row[0])
            for row in conn.execute(
                f"SELECT DISTINCT {column} FROM update_log WHERE tree = ? "
                f"ORDER BY {column}",
                (tree,),
            )
        )
        for column in ("verdict", "action")
    ]
    return found[0], found[1]
