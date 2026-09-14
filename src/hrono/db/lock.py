"""One server per database file, enforced by an advisory lock.

Two ``hrono serve`` processes on one file would run two worker loops racing the
same job queue. The lock is held on a sidecar file for the life of the server
and released by the kernel if the process dies, so a crash never leaves the
database unusable.
"""

from __future__ import annotations

import fcntl
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from hrono.errors import Conflict

SUFFIX = ".lock"


@contextmanager
def exclusive(path: Path) -> Iterator[None]:
    """Hold the only lock on the database at ``path`` for the block.

    Raises ``Conflict`` if another process already holds it.
    """
    lockfile = path.with_name(path.name + SUFFIX)
    lockfile.parent.mkdir(parents=True, exist_ok=True)
    handle = os.open(lockfile, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(handle)
        raise Conflict(
            f"another hrono server is already using {path}",
            details={"database": str(path), "lock": str(lockfile)},
        ) from exc
    try:
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        os.close(handle)
