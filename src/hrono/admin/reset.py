"""Delete the local hrono database and everything that hangs off it.

The wipe only ever touches the resolved hrono database path, its ``-wal`` /
``-shm`` sidecars, its ``.lock`` file and the synced-source cache beside it, and
refuses any path that is not the hrono database file, so it can never remove an
arbitrary file. The cache goes because it is ingested content and the command
says it destroys ingested content (#098, F32): leaving 10 MB of clones behind
meant the next "fresh start" diffed against orphaned trees. Deleting the
database lets the next ``serve`` re-apply migrations onto a fresh file and
re-bootstrap a new admin token. Nothing here prompts or prints; the CLI
boundary owns confirmation.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from hrono.db.database import DEFAULT_PATH
from hrono.db.lock import SUFFIX as LOCK_SUFFIX
from hrono.errors import BadRequest
from hrono.paths import cache_root

_SIDECAR_SUFFIXES = ("-wal", "-shm")


class NotHronoDatabase(BadRequest):
    """The target path is not the hrono database, so it will not be removed."""

    code = "not-hrono-database"


def sidecars(db_path: Path) -> tuple[Path, ...]:
    """Return the ``-wal``/``-shm``/``.lock`` companions of a database file."""
    return tuple(
        db_path.with_name(db_path.name + suffix)
        for suffix in (*_SIDECAR_SUFFIXES, LOCK_SUFFIX)
    )


def targets(db_path: Path = DEFAULT_PATH) -> tuple[Path, ...]:
    """Return the hrono paths that currently exist and would be removed."""
    candidates = (db_path, *sidecars(db_path), cache_root(db_path).parent)
    return tuple(path for path in candidates if path.exists())


def wipe(db_path: Path = DEFAULT_PATH) -> tuple[Path, ...]:
    """Remove the database, its sidecars and its cache; return what went."""
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
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    return removed
