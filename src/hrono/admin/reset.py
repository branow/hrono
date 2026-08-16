"""Delete the local hrono database and its SQLite sidecars for recovery.

The wipe only ever touches the resolved hrono database path and its ``-wal`` /
``-shm`` sidecars, and refuses any path that is not the hrono database file, so
it can never remove an arbitrary file. Deleting the database lets the next
``serve`` re-apply migrations onto a fresh file and re-bootstrap a new admin
token. Nothing here prompts or prints; the CLI boundary owns confirmation.
"""

from __future__ import annotations

from pathlib import Path

from hrono.db.database import DEFAULT_PATH
from hrono.errors import BadRequest

_SIDECAR_SUFFIXES = ("-wal", "-shm")


class NotHronoDatabase(BadRequest):
    """The target path is not the hrono database, so it will not be removed."""

    code = "not-hrono-database"


def sidecars(db_path: Path) -> tuple[Path, ...]:
    """Return the ``-wal``/``-shm`` companion paths for a database file."""
    return tuple(
        db_path.with_name(db_path.name + suffix) for suffix in _SIDECAR_SUFFIXES
    )


def targets(db_path: Path = DEFAULT_PATH) -> tuple[Path, ...]:
    """Return the hrono files that currently exist and would be removed."""
    return tuple(p for p in (db_path, *sidecars(db_path)) if p.exists())


def wipe(db_path: Path = DEFAULT_PATH) -> tuple[Path, ...]:
    """Remove the hrono database and its sidecars; return the files removed."""
    if (
        db_path.name != DEFAULT_PATH.name
        or db_path.parent.name != DEFAULT_PATH.parent.name
    ):
        raise NotHronoDatabase(
            f"refusing to reset a path that is not the hrono database: "
            f"{db_path}"
        )
    removed = targets(db_path)
    for path in removed:
        path.unlink()
    return removed
