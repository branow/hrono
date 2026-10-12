"""The change journal: what each run did to a tree, and how to undo it.

The tables that make up a tree keep only their current rows, so nothing that
reads them changes. Beside them, triggers write every insert, update and
delete a run makes into ``changes``, with the row as it was before. That
journal is the history of every run, the list of what a sync touched, and the
way back: ``revert`` applies a run's entries in reverse.

Which run a write belongs to is a per-thread setting (``recording``), read by
the triggers through the ``journal_run()`` SQL function that every hrono
connection registers. The worker records each job under its run; a write from
anywhere else (a page, a migration) is not journaled.

The triggers are generated from the live schema on every open (``install``),
so every table is journaled unless it is listed in ``UNJOURNALED``, including
tables added later. Each column's old value is kept as an SQL literal
(``quote()``), which round-trips integers, reals, text and blobs exactly.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime

from hrono.errors import Conflict

# Not tree state, or not undoable:
# - bookkeeping of runs, users, keys and configuration, which really happened;
# - the journal itself;
# - content-addressed caches (contents, embeddings, condensations), which a
#   revert leaves in place so syncing again reuses them; they are keyed by
#   content, so a row nothing points at is harmless;
# - the full-text index, a virtual table, rebuilt for the passages a revert
#   touches (``_reindex``).
UNJOURNALED = frozenset(
    {
        "schema_migrations",
        "changes",
        "reverts",
        "jobs",
        "llm_calls",
        "users",
        "keys",
        "registry",
        "recall_log",
        "contents",
        "embeddings",
        "condensations",
        "condense_refusals",
    }
)
_PREFIX = "journal_"

_here = threading.local()


def current() -> str | None:
    """The run this thread's writes are journaled under, if any."""
    return getattr(_here, "run", None)


@contextmanager
def recording(run: str) -> Iterator[None]:
    """Journal this thread's writes under ``run`` for the block."""
    before = current()
    _here.run = run
    try:
        yield
    finally:
        _here.run = before


def register(conn: sqlite3.Connection) -> None:
    """Give ``conn`` the ``journal_run()`` function the triggers call."""
    conn.create_function("journal_run", 0, current)


def install(conn: sqlite3.Connection) -> None:
    """(Re)create the journal triggers for every journaled table."""
    for (name,) in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name LIKE ?",
        (_PREFIX + "%",),
    ).fetchall():
        conn.execute(f'DROP TRIGGER "{name}"')
    for table in journaled(conn):
        for statement in _triggers(table, _columns(conn, table)):
            conn.execute(statement)


def journaled(conn: sqlite3.Connection) -> list[str]:
    """The tables a run's writes are journaled in."""
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    shadows = {
        str(row[0])
        for row in rows
        if str(row[1] or "").upper().startswith("CREATE VIRTUAL TABLE")
    }
    return [
        str(row[0])
        for row in rows
        if str(row[0]) not in UNJOURNALED
        and str(row[0]) not in shadows
        and not any(str(row[0]).startswith(f"{v}_") for v in shadows)
    ]


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    """The columns to keep: all but an INTEGER PRIMARY KEY, which is rowid."""
    info = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    keys = [row for row in info if row[5]]
    alias = (
        str(keys[0][1])
        if len(keys) == 1 and str(keys[0][2]).upper() == "INTEGER"
        else None
    )
    return [str(row[1]) for row in info if str(row[1]) != alias]


def _triggers(table: str, columns: list[str]) -> list[str]:
    old = ", ".join(f"'{c}', quote(OLD.\"{c}\")" for c in columns)
    write = (
        "INSERT INTO changes (run, tbl, op, row, before, created_at) "
        "VALUES (journal_run(), '{t}', '{op}', {row}, {before}, "
        "strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))"
    )
    made = []
    for op, event, row, before in (
        ("insert", "INSERT", "NEW.rowid", "NULL"),
        ("update", "UPDATE", "OLD.rowid", f"json_object({old})"),
        ("delete", "DELETE", "OLD.rowid", f"json_object({old})"),
    ):
        made.append(
            f'CREATE TRIGGER "{_PREFIX}{table}_{op}" AFTER {event} '
            f'ON "{table}" WHEN journal_run() IS NOT NULL BEGIN '
            + write.format(t=table, op=op, row=row, before=before)
            + "; END"
        )
    return made


@dataclass(frozen=True)
class Run:
    """One journaled run: how many rows it changed, and whether undone."""

    run: str
    changes: int
    first: str
    last: str
    reverted: bool


def runs(conn: sqlite3.Connection, limit: int = 50) -> list[Run]:
    """The journaled runs, newest first."""
    return [
        Run(
            run=str(row["run"]),
            changes=int(row["n"]),
            first=str(row["first"]),
            last=str(row["last"]),
            reverted=row["reverted"] is not None,
        )
        for row in conn.execute(
            "SELECT c.run AS run, COUNT(*) AS n, MIN(c.created_at) AS first, "
            "MAX(c.created_at) AS last, r.run AS reverted, MAX(c.id) AS top "
            "FROM changes c LEFT JOIN reverts r ON r.run = c.run "
            "GROUP BY c.run ORDER BY top DESC LIMIT ?",
            (limit,),
        ).fetchall()
    ]


def blocker(conn: sqlite3.Connection, run: str) -> str | None:
    """Why ``run`` cannot be reverted now, or None when it can."""
    if conn.execute("SELECT 1 FROM reverts WHERE run = ?", (run,)).fetchone():
        return "already reverted"
    if not conn.execute(
        "SELECT 1 FROM changes WHERE run = ? LIMIT 1", (run,)
    ).fetchone():
        return "changed nothing"
    if conn.execute(
        "SELECT 1 FROM jobs WHERE status IN ('pending', 'running') LIMIT 1"
    ).fetchone():
        return "a run is in progress"
    newer = conn.execute(
        "SELECT c.run FROM changes c LEFT JOIN reverts r ON r.run = c.run "
        "WHERE r.run IS NULL AND c.id > (SELECT MAX(id) FROM changes "
        "WHERE run = ?) LIMIT 1",
        (run,),
    ).fetchone()
    if newer:
        return f"a later run changed the tree since: revert {newer[0]} first"
    return None


def revert(conn: sqlite3.Connection, run: str, by: str | None) -> int:
    """Undo every change ``run`` made, newest first; how many were undone.

    Runs inside one write transaction. Foreign keys are checked at commit,
    since a parent and its child come back in whatever order they went.
    """
    why = blocker(conn, run)
    if why is not None:
        raise Conflict(
            f"cannot revert {run}: {why}", details={"run": run, "why": why}
        )
    conn.execute("PRAGMA defer_foreign_keys = ON")
    entries = conn.execute(
        "SELECT tbl, op, row, before FROM changes WHERE run = ? "
        "ORDER BY id DESC",
        (run,),
    ).fetchall()
    passages: set[int] = set()
    for entry in entries:
        table, op, row = str(entry["tbl"]), str(entry["op"]), int(entry["row"])
        if table == "passages":
            passages.add(row)
        _UNDO[op](conn, table, row, entry["before"])
    _reindex(conn, passages)
    conn.execute(
        "INSERT INTO reverts (run, reverted_at, reverted_by) VALUES (?, ?, ?)",
        (run, datetime.now(UTC).isoformat(timespec="seconds"), by),
    )
    return len(entries)


def _uninsert(
    conn: sqlite3.Connection, table: str, row: int, before: str | None
) -> None:
    conn.execute(f'DELETE FROM "{table}" WHERE rowid = ?', (row,))


def _unupdate(
    conn: sqlite3.Connection, table: str, row: int, before: str | None
) -> None:
    old: dict[str, str] = json.loads(before or "{}")
    sets = ", ".join(f'"{c}" = {literal}' for c, literal in old.items())
    conn.execute(f'UPDATE "{table}" SET {sets} WHERE rowid = ?', (row,))


def _undelete(
    conn: sqlite3.Connection, table: str, row: int, before: str | None
) -> None:
    old: dict[str, str] = json.loads(before or "{}")
    names = ", ".join(["rowid", *(f'"{c}"' for c in old)])
    values = ", ".join(["?", *old.values()])
    conn.execute(
        f'INSERT INTO "{table}" ({names}) VALUES ({values})',  # noqa: S608
        (row,),
    )


_UNDO = {"insert": _uninsert, "update": _unupdate, "delete": _undelete}


def _reindex(conn: sqlite3.Connection, passages: set[int]) -> None:
    """Bring the full-text index back in line with the passages restored."""
    ids = sorted(passages)
    for start in range(0, len(ids), 500):
        chunk = ids[start : start + 500]
        marks = ",".join("?" * len(chunk))
        conn.execute(
            f"DELETE FROM passages_fts WHERE passage_id IN ({marks})",  # noqa: S608
            chunk,
        )
        conn.execute(
            "INSERT INTO passages_fts (passage_id, source, path, body) "  # noqa: S608
            "SELECT p.id, p.source, p.path, CAST(c.body AS TEXT) "
            "FROM passages p JOIN contents c "
            "ON c.content_hash = p.content_hash "
            f"WHERE p.id IN ({marks})",
            chunk,
        )
