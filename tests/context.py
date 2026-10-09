"""Build a ``JobContext`` the way the server does, anchored on the database.

The worker resolves the cache root from the database path at startup and
hands it to every op; tests that drive an ingest op need the same anchor, so
they build their context here instead of relying on the process working
directory.
"""

from __future__ import annotations

from pathlib import Path

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
from hrono.jobs.ops import JobContext
from hrono.paths import cache_root


def job_context(
    database: Database, root: Path, cipher: Cipher | None = None
) -> JobContext:
    """The context a worker would build for a database at ``root/hrono.db``."""
    return JobContext(database, cipher, cache_root(root / "hrono.db"))
