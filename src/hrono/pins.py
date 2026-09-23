"""Pins: the hard constraint a hand-edit leaves behind (#154, T45).

The spec's rule, in one sentence: "A hand-edit pins the entity, and the
pipeline treats a pin as a hard constraint ... Without this, a manual fix gets
silently reverted on the next update."

Three kinds today, and the kind says what is held rather than which table it
lives in:

- ``brief`` — this node's summary is the operator's, and ``brief`` /
  ``brief-upper`` must not rewrite it.
- ``membership`` — this SECTION belongs where a human put it, and no migration
  may move it.
- ``parenting`` — this NODE hangs where a human put it, and no upper-level
  migration may re-attach it.

Pinning is a consequence of editing, never a separate call the operator has to
remember; ``unpin`` is the only explicit pin operation. This module is the
whole vocabulary — it imports nothing of hrono's, so every layer can ask.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime

BRIEF = "brief"
MEMBERSHIP = "membership"
PARENTING = "parenting"
KINDS = (BRIEF, MEMBERSHIP, PARENTING)


def pin(
    conn: sqlite3.Connection,
    kind: str,
    target_id: int,
    reason: str | None = None,
) -> None:
    """Hold ``target_id`` against the pipeline; re-pinning refreshes the why."""
    if kind not in KINDS:
        raise ValueError(f"unknown pin kind: {kind}")
    conn.execute(
        "INSERT INTO pins(kind, target_id, reason, pinned_at) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(kind, target_id) DO UPDATE SET "
        "reason = excluded.reason, pinned_at = excluded.pinned_at",
        (kind, target_id, reason, _now()),
    )


def unpin(conn: sqlite3.Connection, kind: str, target_id: int) -> bool:
    """Hand it back to automation; True when something was actually held."""
    cursor = conn.execute(
        "DELETE FROM pins WHERE kind = ? AND target_id = ?", (kind, target_id)
    )
    return cursor.rowcount > 0


def unpin_all(conn: sqlite3.Connection, target_id: int) -> int:
    """Release every pin on one node — what "hand this back" means (#156)."""
    cursor = conn.execute(
        "DELETE FROM pins WHERE kind IN (?, ?) AND target_id = ?",
        (BRIEF, PARENTING, target_id),
    )
    return cursor.rowcount


def is_pinned(conn: sqlite3.Connection, kind: str, target_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM pins WHERE kind = ? AND target_id = ?",
        (kind, target_id),
    ).fetchone()
    return row is not None


def pinned(conn: sqlite3.Connection, kind: str) -> frozenset[int]:
    """Every id held for ``kind`` — read once, then asked many times."""
    return frozenset(
        int(row["target_id"])
        for row in conn.execute(
            "SELECT target_id FROM pins WHERE kind = ?", (kind,)
        ).fetchall()
    )


def reasons(
    conn: sqlite3.Connection, target_id: int, kinds: Iterable[str] = KINDS
) -> dict[str, str | None]:
    """What is held on this id and why, for an operator asking about it."""
    marks = ",".join("?" * len(tuple(kinds)))
    rows = conn.execute(
        f"SELECT kind, reason FROM pins WHERE target_id = ? "  # noqa: S608
        f"AND kind IN ({marks})",
        (target_id, *kinds),
    ).fetchall()
    return {str(row["kind"]): row["reason"] for row in rows}


def _now() -> str:
    return datetime.now(UTC).isoformat()
