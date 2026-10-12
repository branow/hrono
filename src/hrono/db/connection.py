"""The single owner of hrono's SQLite database file."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec

from hrono.db import journal

_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA busy_timeout=5000",
    "PRAGMA synchronous=NORMAL",
    # an INSERT OR REPLACE deletes the row it replaces, and only with this on
    # does that delete fire a trigger, so the change journal keeps the old row
    "PRAGMA recursive_triggers=ON",
)


def connect(path: Path, *, extensions: bool = True) -> sqlite3.Connection:
    """Open a configured connection to the hrono database.

    WAL, foreign-key enforcement and a busy timeout are applied before any
    transaction opens, since WAL cannot be switched from inside one. Set
    ``extensions`` false to skip sqlite-vec when the caller never touches
    vectors.

    Transactions are ``IMMEDIATE``: a read runs outside any transaction, so it
    always sees the newest commit and can never pin a WAL snapshot, and a write
    takes the write lock up front instead of discovering a conflict on upgrade
    (a mid-transaction SQLITE_BUSY that can wedge the server).

    ``check_same_thread`` is disabled because a connection may be borrowed by
    whichever thread asked for it; ``Database`` hands one connection to one
    thread at a time.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    journal.register(conn)
    for pragma in _PRAGMAS:
        conn.execute(pragma)
    if extensions:
        _load_extensions(conn)
    conn.isolation_level = "IMMEDIATE"
    return conn


def _load_extensions(conn: sqlite3.Connection) -> None:
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
