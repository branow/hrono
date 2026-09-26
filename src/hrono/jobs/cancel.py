"""Stopping a run that is already going (T57.2, #173).

COOPERATIVE, and the unit it cooperates at is a JOB. A pending job is stopped
outright; a running one is left to finish, because the only way to stop a
handler mid-flight is to kill the thread it is on, and #092 exists because a
transaction interrupted halfway is how this database gets corrupted.

That is a real limit and the response says so rather than implying otherwise: a
cancel reports how many jobs it STOPPED and how many are still running. An
operator who cancels a fan-out over forty sources and is told "39 stopped, 1
still finishing" knows exactly where they are. One that said "canceled" would
be lying about the stage still writing.

Cancel is not an undo: a job that already succeeded or failed keeps its
outcome.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from hrono.jobs import store
from hrono.jobs.model import JobStatus


@dataclass(frozen=True)
class Cancellation:
    """What a cancel could and could not stop."""

    stopped: int
    running: int
    finished: int


def cancel(conn: sqlite3.Connection, job_id: str) -> Cancellation:
    """Stop what can be stopped under ``job_id``; report the rest.

    A parent cancels its CHILDREN — they are the units of work, and the parent
    row is not one. Its own status is derived from them (#172), so a parent
    whose children are all canceled reads as canceled without anything writing
    that to its row and creating a second source of truth.

    The update is one statement guarded by ``status = 'pending'``, so a child
    that the worker claimed between the read and the write is not overwritten:
    it counts as running, which is what it is.
    """
    targets = [row["id"] for row in store.children(conn, job_id)] or [job_id]
    marks = ",".join("?" * len(targets))
    now = datetime.now(UTC).isoformat()
    with conn:
        cursor = conn.execute(
            "UPDATE jobs SET status = ?, updated_at = ? "  # noqa: S608
            f"WHERE id IN ({marks}) AND status = ?",
            (JobStatus.CANCELED, now, *targets, JobStatus.PENDING),
        )
    stopped = int(cursor.rowcount)
    rows = [store.get(conn, target) for target in targets]
    running = sum(
        1 for row in rows if row is not None and row["status"] == "running"
    )
    return Cancellation(
        stopped=stopped,
        running=running,
        finished=len(targets) - stopped - running,
    )
