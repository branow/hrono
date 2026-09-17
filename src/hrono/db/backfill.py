"""Data steps that belong to a schema migration, in Python rather than SQL.

A forward-only migration sometimes has to move DATA, not just shape: #102's
`0024_brief_members` takes the member list out of `briefs.text` and stores it
beside the brief, and the rows already written have to move with it or the
change applies only to briefs that do not exist yet. Some of that surgery is not
expressible in SQL — re-splitting a brief into #071 passages is the packer's job
— so a version may register a Python step here and the runner applies it in the
same transaction as that version's ``.sql``.

Steps must be pure functions of the connection, idempotent, and safe on an
empty database: they run once per database, guarded by the same bookkeeping
that guards the SQL.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable

_SENTINELS = ("\n\nReferences:\n", "\n\nChildren:\n")


def brief_members(conn: sqlite3.Connection) -> None:
    """Move each brief's member footer into ``briefs.members`` and re-split it.

    The footers are machine-written (``brief``/``brief_upper`` appended them
    from a fixed format), so this is a ``partition`` on a constant sentinel and
    a strip of "- " per line, not prose parsing: a line that does not match the
    format aborts the move for that brief and leaves it untouched. Re-splitting
    through ``store_brief`` rebuilds the node:// section AND its passages, so
    the index stops carrying reference lists as if they were prose.
    """
    from hrono.ingest.store import clear_source
    from hrono.recall import fts
    from hrono.recall.brief_passages import store_brief

    for source in _orphaned_sources(conn):
        clear_source(conn, source)
        fts.clear_source(conn, source)

    rows = conn.execute(
        "SELECT node_id, text, member_signature FROM briefs ORDER BY node_id"
    ).fetchall()
    for row in rows:
        moved = _partition(row["text"])
        if moved is None:
            continue
        prose, members = moved
        conn.execute(
            "UPDATE briefs SET text = ?, members = ? WHERE node_id = ?",
            (prose, json.dumps(members), int(row["node_id"])),
        )
        store_brief(conn, int(row["node_id"]), prose, row["member_signature"])


def _orphaned_sources(conn: sqlite3.Connection) -> tuple[str, ...]:
    """node:// sources whose node no longer exists.

    A retired node's brief cascades with it, but its #071 passages are keyed by
    SOURCE and nothing cascades those — so the index keeps serving summaries of
    topics the map no longer holds, footers and all. Measured on the QA corpus:
    51 of 85 node:// passages belonged to three retired nodes. Clearing them is
    part of taking the reference lists out of the index; stopping them being
    created is #125, at the retirement site.
    """
    return tuple(
        row["source"]
        for row in conn.execute(
            "SELECT DISTINCT s.source AS source FROM sections s "
            "WHERE s.source_type = 'node' AND NOT EXISTS ("
            "  SELECT 1 FROM nodes n "
            "  WHERE 'node-' || n.id = s.source)"
        ).fetchall()
    )


def _partition(text: str) -> tuple[str, list[str]] | None:
    """Split a brief into (prose, members), or None when it has no footer."""
    for sentinel in _SENTINELS:
        head, found, tail = text.partition(sentinel)
        if not found:
            continue
        lines = [line for line in tail.splitlines() if line.strip()]
        if not all(line.startswith("- ") for line in lines):
            return None  # not the machine format: leave the brief alone
        return head.rstrip(), [line[2:].strip() for line in lines]
    return None


Step = Callable[[sqlite3.Connection], None]

STEPS: dict[int, Step] = {24: brief_members}
