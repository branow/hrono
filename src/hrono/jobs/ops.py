"""The op registry: a data-driven name -> handler map the worker dispatches on.

A new op (sync, split, embed, ...) registers an entry; the worker never branches
on op name. One trivial built-in (``noop``) makes the loop driveable before real
ops exist.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
from hrono.errors import Internal
from hrono.jobs.model import Job


@dataclass(frozen=True)
class JobContext:
    """What an op handler needs to do its work (grows with the ops).

    ``cipher`` is None only when no op in play needs to decrypt a secret (tests
    of secretless ops); real ingest ops that read source auth require it.
    ``cache_root`` is where this database's synced clones live (#098): the
    server resolves it from the database path at startup and it is passed here,
    never re-derived from the working directory. It is None only for a context
    whose ops never touch the cache — asking for a path then is a bug, not a
    reason to guess a location, so ``cache_for`` raises. ``job_id`` is the job
    the worker is running, which every model call is recorded against (#201);
    None for an op driven directly, outside any job.
    """

    database: Database
    cipher: Cipher | None = None
    cache_root: Path | None = None
    job_id: str | None = None

    def cli_dir(self) -> Path:
        """Where a subprocess LLM backend runs (#107), beside the clone cache.

        Derived from the same anchor as ``cache_for`` rather than re-resolved
        from the database path, so nothing downstream can point a subprocess at
        a directory the server did not choose.
        """
        if self.cache_root is None:
            raise Internal(
                "no cache root: this job context cannot run a CLI backend"
            )
        return self.cache_root.parent / "cli"

    def cache_for(self, source: str) -> Path:
        """The synced clone directory for ``source`` under this cache root."""
        if self.cache_root is None:
            raise Internal(
                "no cache root: this job context cannot run ingest ops",
                details={"source": source},
            )
        return self.cache_root / source


Handler = Callable[[Job, JobContext], Mapping[str, object] | None]


def _noop(job: Job, context: JobContext) -> None:
    """Do nothing — proves the loop end to end."""
    return None


OPS: dict[str, Handler] = {"noop": _noop}
