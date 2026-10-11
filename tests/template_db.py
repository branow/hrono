"""A migrated database, made once per process and copied into each new one.

Opening a new database runs every packaged migration, about twenty
milliseconds, and the suite opens one in nearly every test. Here the first
open in a process migrates a template file; every later open of an EMPTY
database copies the template's pages in (SQLite's backup API) and then runs
the real migration runner, which finds nothing pending. The copy is the same
schema the runner would have built, in the same WAL mode, so a test cannot
tell, except that ``schema_migrations.applied_at`` says when the template was
migrated rather than when the test began.

A database that already has tables is left to the real runner untouched, and
``tests/db`` turns the copy off so the migration tests watch the runner build
every schema itself.
"""

from __future__ import annotations

import atexit
import shutil
import sqlite3
import tempfile
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from hrono.db import database
from hrono.db.connection import connect
from hrono.db.migrations import migrate

_lock = threading.Lock()
_template: sqlite3.Connection | None = None
_enabled = True


def install() -> None:
    """Route ``open_database`` through the template from now on."""
    database.migrate = _migrate  # type: ignore[attr-defined]


@contextmanager
def real_migrations() -> Iterator[None]:
    """Every database opened inside is migrated by the runner alone."""
    global _enabled
    previous, _enabled = _enabled, False
    try:
        yield
    finally:
        _enabled = previous


def _migrate(conn: sqlite3.Connection) -> tuple[int, ...]:
    if _enabled and _empty(conn):
        with _lock:
            _source().backup(conn)
    return migrate(conn)


def _empty(conn: sqlite3.Connection) -> bool:
    return (
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchone() is None
    )


def _source() -> sqlite3.Connection:
    global _template
    if _template is None:
        folder = Path(tempfile.mkdtemp(prefix="hrono-template-"))
        made = connect(folder / "template.db")
        migrate(made)
        _template = made
        atexit.register(_discard, made, folder)
    return _template


def _discard(made: sqlite3.Connection, folder: Path) -> None:
    made.close()
    shutil.rmtree(folder, ignore_errors=True)
