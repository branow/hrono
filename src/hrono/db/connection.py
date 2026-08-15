"""The single owner of hrono's SQLite database file."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import sqlite_vec

_PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA foreign_keys=ON",
    "PRAGMA busy_timeout=5000",
    "PRAGMA synchronous=NORMAL",
)


def connect(path: Path, *, extensions: bool = True) -> sqlite3.Connection:
    """Open a configured connection to the hrono database.

    WAL, foreign-key enforcement and a busy timeout are applied before any
    transaction opens, since WAL cannot be switched from inside one. The
    connection is handed back in transactional mode (autocommit off) so callers
    own their commits. Set ``extensions`` false to skip sqlite-vec when the
    caller never touches vectors.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, autocommit=True)
    conn.row_factory = sqlite3.Row
    for pragma in _PRAGMAS:
        conn.execute(pragma)
    if extensions:
        _load_extensions(conn)
    conn.autocommit = False
    return conn


def _load_extensions(conn: sqlite3.Connection) -> None:
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
