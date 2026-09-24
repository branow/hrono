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
    anchor: int | None = None,
) -> None:
    """Hold ``target_id`` against the pipeline; re-pinning refreshes the why.

    ``anchor`` says WHERE, for the kinds that need one: the node a membership
    must stay in, the parent a child must hang under. A brief anchors nothing —
    it is held in place by being itself (#155).
    """
    if kind not in KINDS:
        raise ValueError(f"unknown pin kind: {kind}")
    conn.execute(
        "INSERT INTO pins(kind, target_id, reason, pinned_at, anchor_id) "
        "VALUES (?, ?, ?, ?, ?) ON CONFLICT(kind, target_id) DO UPDATE SET "
        "reason = excluded.reason, pinned_at = excluded.pinned_at, "
        "anchor_id = excluded.anchor_id",
        (kind, target_id, reason, _now(), anchor),
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


def reanchor(
    conn: sqlite3.Connection, kind: str, target_id: int, anchor: int
) -> None:
    """Point an existing pin at a new node, keeping its reason and its date.

    A split retires the node an anchor names and hands its members to fresh
    children (#162). The operator's decision has not changed and neither has
    when they made it — only the id that expresses it — so this is an UPDATE
    of the address and not a re-pin, which would rewrite the reason with
    whatever the pipeline happened to be doing at the time.
    """
    conn.execute(
        "UPDATE pins SET anchor_id = ? WHERE kind = ? AND target_id = ?",
        (anchor, kind, target_id),
    )


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


def anchors(conn: sqlite3.Connection, kind: str) -> dict[int, int]:
    """target -> anchor for every pin of ``kind`` that names one.

    Read once per run and asked per candidate: the pipeline decides this for
    every member of every cluster, and a query per decision would put a pin's
    cost on the corpus rather than on the pins.
    """
    return {
        int(row["target_id"]): int(row["anchor_id"])
        for row in conn.execute(
            "SELECT target_id, anchor_id FROM pins "
            "WHERE kind = ? AND anchor_id IS NOT NULL",
            (kind,),
        ).fetchall()
    }


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
