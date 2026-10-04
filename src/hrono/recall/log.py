"""The recall log (E042): what agents asked, bounded per tree.

Only the API's recall route writes here. The Ask page asks the same question
through the same engine and leaves no row: its asker is a curator checking
the tree, and counting that as agent use would hide the thing the log is for.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from typing import TypedDict

from hrono.recall.engine import Recall

KEEP = 10_000
QUESTION_CHARS = 500


def record(
    conn: sqlite3.Connection, tree: str, user: str, got: Recall, question: str
) -> None:
    """Add one row for this recall and drop the rows past ``KEEP``.

    The question is cut to ``QUESTION_CHARS`` so the cap bounds bytes and not
    only rows.
    """
    conn.execute(
        "INSERT INTO recall_log(tree, user, question, hits, top_score, "
        "confident, asked_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            tree,
            user,
            question[:QUESTION_CHARS],
            len(got.hits),
            got.hits[0].score if got.hits else None,
            int(bool(got.hits)),
            datetime.now(UTC).isoformat(),
        ),
    )
    conn.execute(
        "DELETE FROM recall_log WHERE tree = ? AND id <= ("
        "SELECT id FROM recall_log WHERE tree = ? "
        "ORDER BY id DESC LIMIT 1 OFFSET ?)",
        (tree, tree, KEEP),
    )


class Day(TypedDict):
    """One day's calls and how many of them were not confident."""

    day: str
    calls: int
    unsure: int


def per_day(conn: sqlite3.Connection, tree: str) -> list[Day]:
    """Calls and refusals per day, oldest first."""
    rows = conn.execute(
        "SELECT substr(asked_at, 1, 10) AS day, COUNT(*) AS calls, "
        "SUM(1 - confident) AS unsure FROM recall_log WHERE tree = ? "
        "GROUP BY day ORDER BY day",
        (tree,),
    ).fetchall()
    return [
        Day(day=row["day"], calls=row["calls"], unsure=row["unsure"])
        for row in rows
    ]


def latest(
    conn: sqlite3.Connection, tree: str, limit: int
) -> list[dict[str, object]]:
    """The newest questions first, with who asked and how many hits."""
    rows = conn.execute(
        "SELECT user, question, hits, confident, asked_at FROM recall_log "
        "WHERE tree = ? ORDER BY id DESC LIMIT ?",
        (tree, limit),
    ).fetchall()
    return [dict(row) for row in rows]
