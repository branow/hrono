"""Where hrono's on-disk data lives — every location anchored on the database.

The database file is the anchor, not the process working directory (#098, F25):
the synced source clones live in ``<db parent>/cache/sources``, so two processes
started from different directories against the same ``--db`` read and write ONE
cache. Before this, the cache root was a module constant resolved against cwd,
so a server started in one directory and an op driver started in another kept
two divergent clone sets for the same database — and diffing the database
against the stale one invented changes, including a reversed rename.

The resolved path is absolute: it is read once at startup and then passed
around, so nothing downstream can re-resolve it against a different cwd.
"""

from __future__ import annotations

import os
from pathlib import Path

from hrono.db.database import DEFAULT_PATH

ENV_DB = "HRONO_DB"


def database_path(explicit: Path | None = None) -> Path:
    """Resolve the database: ``--db``, else ``$HRONO_DB``, else the default."""
    if explicit is not None:
        return _absolute(explicit)
    from_env = os.environ.get(ENV_DB)
    return _absolute(Path(from_env) if from_env else DEFAULT_PATH)


def cache_root(db_path: Path) -> Path:
    """The synced-source clone root for the database at ``db_path``."""
    return db_path.parent / "cache" / "sources"


def _absolute(path: Path) -> Path:
    return path.expanduser().resolve()
