"""Opening the hrono database: connect, then bring the schema up to date.

The server calls this once at startup and holds the returned connection as the
single writer for its lifetime.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

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
