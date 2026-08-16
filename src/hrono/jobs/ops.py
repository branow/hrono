"""The op registry: a data-driven name -> handler map the worker dispatches on.

A new op (sync, split, embed, ...) registers an entry; the worker never branches
on op name. One trivial built-in (``noop``) makes the loop driveable before real
ops exist.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from hrono.db.database import Database
from hrono.jobs.model import Job


@dataclass(frozen=True)
class JobContext:
    """What an op handler needs to do its work (grows with the ops)."""

    database: Database


Handler = Callable[[Job, JobContext], None]


def _noop(job: Job, context: JobContext) -> None:
    """Do nothing — proves the loop end to end."""
    return None


OPS: dict[str, Handler] = {"noop": _noop}
