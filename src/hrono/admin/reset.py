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

Two rules keep a destructive command honest when the layout is not the plain
one:

- a cache that is a SYMLINK is refused, before anything is deleted. The
  recursive delete is only safe because it is bounded by the ``.hrono``
  directory the guard above proves; a link points outside that bound, and
  hrono cannot know what else lives at the other end. Unlinking instead would
  leave the clones on disk while the command claims to have destroyed ingested
  content — the very claim F32 is about — so this refuses and says what to do.
- any ``OSError`` while removing (permissions, a busy file, a full disk) stops
  the wipe and is raised as ``ResetIncomplete`` carrying what HAD been removed,
  because a half-done destructive command is exactly when the operator needs
  that list.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from hrono.db.database import DEFAULT_PATH
from hrono.db.lock import SUFFIX as LOCK_SUFFIX
from hrono.errors import BadRequest, Internal
from hrono.paths import cache_root

_SIDECAR_SUFFIXES = ("-wal", "-shm")


class NotHronoDatabase(BadRequest):
    """The target path is not the hrono database, so it will not be removed."""

    code = "not-hrono-database"


class LinkedCache(BadRequest):
    """The cache is a symlink, so the wipe cannot bound what it would delete."""

    code = "linked-cache"


class ResetIncomplete(Internal):
    """The wipe stopped part-way; ``details['removed']`` is what did go."""

    code = "reset-incomplete"


def sidecars(db_path: Path) -> tuple[Path, ...]:
    """Return the ``-wal``/``-shm``/``.lock`` companions of a database file."""
    return tuple(
        db_path.with_name(db_path.name + suffix)
        for suffix in (*_SIDECAR_SUFFIXES, LOCK_SUFFIX)
    )


def cache(db_path: Path) -> Path:
    """The ingest cache directory belonging to the database at ``db_path``."""
    return cache_root(db_path).parent


def targets(db_path: Path = DEFAULT_PATH) -> tuple[Path, ...]:
    """Return the hrono paths that currently exist and would be removed."""
    candidates = (db_path, *sidecars(db_path), cache(db_path))
    return tuple(path for path in candidates if path.exists())


def wipe(db_path: Path = DEFAULT_PATH) -> tuple[Path, ...]:
    """Remove the database, its sidecars and its cache; return what went."""
    _refuse_foreign_path(db_path)
    _refuse_linked_cache(cache(db_path))
    removed: list[Path] = []
    for path in targets(db_path):
        try:
            _remove(path)
        except OSError as exc:
            raise ResetIncomplete(
                f"reset stopped at {path}: {exc.strerror or exc}",
                details={
                    "removed": [str(done) for done in removed],
                    "failed": str(path),
                },
            ) from exc
        removed.append(path)
    return tuple(removed)


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def _refuse_foreign_path(db_path: Path) -> None:
    if (
        db_path.name != DEFAULT_PATH.name
        or db_path.parent.name != DEFAULT_PATH.parent.name
    ):
        raise NotHronoDatabase(
            f"refusing to reset a path that is not the hrono database: "
            f"{db_path}"
        )


def _refuse_linked_cache(path: Path) -> None:
    if not path.is_symlink():
        return
    raise LinkedCache(
        f"refusing to reset: the cache {path} is a symlink, so what it would "
        f"delete is not bounded by {path.parent}. Remove or re-point the link, "
        f"then reset again. Nothing was removed.",
        details={"cache": str(path), "target": str(path.resolve())},
    )
