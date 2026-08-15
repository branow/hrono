"""Opening the hrono database: connect, then bring the schema up to date.

The server calls this once at startup and holds the returned connection as the
single writer for its lifetime.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from hrono.db.connection import connect
from hrono.db.migrations import migrate

DEFAULT_PATH = Path(".hrono/hrono.db")


def open_database(path: Path = DEFAULT_PATH) -> sqlite3.Connection:
    """Open the hrono database at ``path`` with pending migrations applied.

    Returns a connection whose schema is up to date; idempotent across restarts
    since the migration runner only applies what is missing.
    """
    conn = connect(path)
    migrate(conn)
    return conn


class Database:
    """Owns the single sqlite connection and serializes all access to it.

    A lone ``sqlite3.Connection`` is not safe for concurrent cross-thread use
    even for reads, so every operation acquires one lock; this keeps the
    "one server, one writer" guarantee while letting sync route handlers, which
    FastAPI runs in a threadpool, use the connection without cross-thread
    errors.
    """

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._lock = RLock()

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield the connection with exclusive access held for the block."""
        with self._lock:
            yield self._connection

    def close(self) -> None:
        self._connection.close()
