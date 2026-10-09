"""Opening the hrono database and handing out connections to work on it.

The server borrows a connection per operation rather than sharing one for the
whole process: a connection that an op left mid-transaction is rolled back and
dropped back into the pool clean, so one failure cannot pin a stale snapshot or
hold the write lock for every other caller.
"""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Lock, RLock, local
from typing import Protocol

from hrono.db.connection import connect
from hrono.db.migrations import migrate
from hrono.errors import Unavailable

DEFAULT_PATH = Path(".hrono/hrono.db")

POOL_SIZE = 4

_BUSY_ATTEMPTS = 4
_BUSY_BACKOFF = 0.05


@contextmanager
def tx(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """One transaction around a block — WITHOUT committing a caller's.

    ``with conn:`` commits whatever transaction is open on exit, so a store
    function using it inside ``Database.write()`` committed the outer
    ``BEGIN IMMEDIATE`` early and released the write lock in the middle of a
    block that promises one transaction — ``rotate_running``'s "rekey under
    the same lock" was false exactly this way. Inside an open transaction this
    joins it (the owner commits or rolls back); outside one it behaves as
    ``with conn:`` always did.
    """
    if conn.in_transaction:
        yield conn
        return
    with conn:
        yield conn


def open_database(path: Path = DEFAULT_PATH) -> sqlite3.Connection:
    """Open the hrono database at ``path`` with pending migrations applied.

    Returns a connection whose schema is up to date; idempotent across restarts
    since the migration runner only applies what is missing.
    """
    conn = connect(path)
    migrate(conn)
    return conn


class Connections(Protocol):
    """Where a ``Database`` gets a connection to lend out."""

    def acquire(self) -> sqlite3.Connection: ...

    def release(
        self, connection: sqlite3.Connection, *, reusable: bool
    ) -> None: ...

    def close(self) -> None: ...


class Pool:
    """Reusable connections to one database file, ``size`` kept idle."""

    def __init__(self, path: Path, size: int = POOL_SIZE) -> None:
        self._path = path
        self._size = size
        self._guard = Lock()
        self._closed = False
        self._idle: list[sqlite3.Connection] = [open_database(path)]

    def acquire(self) -> sqlite3.Connection:
        with self._guard:
            if self._idle:
                return self._idle.pop()
        return connect(self._path)

    def release(
        self, connection: sqlite3.Connection, *, reusable: bool
    ) -> None:
        if reusable:
            with self._guard:
                if not self._closed and len(self._idle) < self._size:
                    self._idle.append(connection)
                    return
        connection.close()

    def close(self) -> None:
        """Close the idle set and refuse new parking.

        Without the flag, a worker thread outliving the 5 s shutdown join
        could release its connection AFTER this ran, parking a live handle in
        a pool nobody will ever drain — an open file descriptor per restart.
        """
        with self._guard:
            self._closed = True
            idle, self._idle = self._idle, []
        for connection in idle:
            connection.close()


class Shared:
    """One connection owned by the caller, lent to one thread at a time."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection
        self._guard = RLock()

    def acquire(self) -> sqlite3.Connection:
        self._guard.acquire()
        return self._connection

    def release(
        self, connection: sqlite3.Connection, *, reusable: bool
    ) -> None:
        self._guard.release()

    def close(self) -> None:
        """No-op: the caller that supplied the connection closes it."""


class Database:
    """Lends connections out for the length of one block, and takes them back
    clean.

    ``connect`` is the read door and ``write`` the write door; both return the
    connection to the pool with no transaction open, whether the block
    succeeded or raised. Nested borrows on one thread reuse that thread's
    connection, so an op calling into another op shares its transaction instead
    of deadlocking against itself.
    """

    def __init__(self, connections: Connections) -> None:
        self._connections = connections
        self._held = local()

    @classmethod
    def at(cls, path: Path, *, size: int = POOL_SIZE) -> Database:
        """Own a pool against the database file at ``path`` (migrating it)."""
        return cls(Pool(path, size))

    @classmethod
    def adopt(cls, connection: sqlite3.Connection) -> Database:
        """Borrow a connection someone else opened, and never close it."""
        return cls(Shared(connection))

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection for the block; commit it, or roll it back."""
        held: sqlite3.Connection | None = getattr(self._held, "conn", None)
        if held is not None:
            yield held
            return
        conn = self._connections.acquire()
        self._held.conn = conn
        reusable = True
        try:
            yield conn
        except BaseException as exc:
            reusable = _rollback(conn)
            mapped = _mapped(exc)
            if mapped is exc:
                raise
            raise mapped from exc
        else:
            if conn.in_transaction:
                conn.commit()
        finally:
            self._held.conn = None
            self._connections.release(conn, reusable=reusable)

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        """Yield a connection inside one ``BEGIN IMMEDIATE`` transaction.

        The write lock is taken before the block runs, with bounded retries on
        top of the busy timeout, so a writer that loses a race waits instead of
        failing its job.
        """
        with self.connect() as conn:
            if conn.in_transaction:
                yield conn
                return
            _begin(conn)
            yield conn
            if conn.in_transaction:
                conn.commit()

    def probe(self) -> dict[str, object]:
        """Report whether the database answers, for the health endpoint."""
        with self.connect() as conn:
            answer = conn.execute("SELECT 1").fetchone()[0]
            return {"ok": answer == 1, "in_transaction": conn.in_transaction}

    def close(self) -> None:
        self._connections.close()


def _begin(conn: sqlite3.Connection) -> None:
    for attempt in range(_BUSY_ATTEMPTS):
        try:
            conn.execute("BEGIN IMMEDIATE")
        except sqlite3.OperationalError as exc:
            if attempt == _BUSY_ATTEMPTS - 1 or not _busy(exc):
                raise
            time.sleep(_BUSY_BACKOFF * 2**attempt)
        else:
            return


def _rollback(conn: sqlite3.Connection) -> bool:
    """Undo what the failed block left open; report the connection usable."""
    try:
        conn.rollback()
    except sqlite3.Error:
        return False
    return True


def _mapped(exc: BaseException) -> BaseException:
    if isinstance(exc, sqlite3.OperationalError) and _busy(exc):
        return Unavailable("database is busy, try again shortly")
    return exc


def _busy(exc: sqlite3.OperationalError) -> bool:
    return "locked" in str(exc) or "busy" in str(exc)
