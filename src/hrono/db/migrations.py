"""Forward-only SQL schema migrations.

Migrations are plain ``.sql`` files named ``NNNN_description.sql``. The runner
applies every unapplied migration in version order, each in its own
transaction, and records it in ``schema_migrations`` so re-runs are a no-op.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_FILENAME = re.compile(r"^(\d+)_([a-z0-9_]+)\.sql$")

_PACKAGED = Path(__file__).parent / "migrations"

_BOOKKEEPING = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    statements: str


class DuplicateVersion(Exception):
    """Two migration files claim the same version number."""

    def __init__(self, version: int) -> None:
        super().__init__()
        self.version = version


def discover(directory: Path) -> tuple[Migration, ...]:
    """Load migrations from ``directory``, ordered by version.

    Files not matching ``NNNN_description.sql`` are ignored, so editor
    scratch files and READMEs can live alongside migrations.
    """
    found: dict[int, Migration] = {}
    for file in sorted(directory.glob("*.sql")):
        match = _FILENAME.match(file.name)
        if match is None:
            continue
        version = int(match.group(1))
        if version in found:
            raise DuplicateVersion(version)
        found[version] = Migration(version, match.group(2), file.read_text())
    return tuple(found[version] for version in sorted(found))


class Migrator:
    """Applies a fixed set of migrations against a connection."""

    def __init__(self, migrations: tuple[Migration, ...]) -> None:
        self._migrations = tuple(sorted(migrations, key=lambda m: m.version))

    def pending(self, conn: sqlite3.Connection) -> tuple[Migration, ...]:
        applied = self._applied(conn)
        return tuple(m for m in self._migrations if m.version not in applied)

    def apply(self, conn: sqlite3.Connection) -> tuple[int, ...]:
        """Apply every pending migration; return the versions applied."""
        pending = self.pending(conn)
        for migration in pending:
            with _atomic(conn), conn:
                conn.executescript(migration.statements)
                conn.execute(
                    "INSERT INTO schema_migrations(version, name, "
                    "applied_at) VALUES (?, ?, ?)",
                    (migration.version, migration.name, _now()),
                )
        return tuple(m.version for m in pending)

    def _applied(self, conn: sqlite3.Connection) -> frozenset[int]:
        with conn:
            conn.execute(_BOOKKEEPING)
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
        return frozenset(row[0] for row in rows)


@contextmanager
def _atomic(conn: sqlite3.Connection) -> Iterator[None]:
    """Run a migration script and its bookkeeping row as one transaction.

    ``executescript`` commits whatever is pending before it runs, so an
    explicit ``BEGIN`` cannot wrap it; PEP 249 transaction control can, and is
    restored (with the transaction closed) before the connection goes back to
    normal ``IMMEDIATE`` use.
    """
    previous = conn.autocommit
    conn.autocommit = False
    try:
        yield
    finally:
        conn.autocommit = previous
        conn.commit()


def packaged() -> tuple[Migration, ...]:
    """Discover the migrations shipped inside the installed hrono package.

    Resolved relative to this module, so it works from an installed package
    and never depends on the current working directory.
    """
    return discover(_PACKAGED)


def migrate(conn: sqlite3.Connection) -> tuple[int, ...]:
    """Apply every pending packaged migration to ``conn``."""
    return Migrator(packaged()).apply(conn)


def _now() -> str:
    return datetime.now(UTC).isoformat()
