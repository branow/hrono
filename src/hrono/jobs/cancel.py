"""Stopping a run that is already going.

COOPERATIVE. A pending job is stopped outright. A running one is SIGNALED: its
row flips to ``canceled``, which is the predicate ``pool.running`` polls
between LLM calls, so a long op halts at its next checkpoint — but the thread
is never killed (a transaction interrupted halfway is how this database gets
corrupted), so the step in flight still finishes and its writes are kept.

The response says exactly that: a cancel reports how many jobs it STOPPED and
how many are still winding down. An operator who cancels a fan-out over forty
sources and is told "39 stopped, 1 still finishing" knows exactly where they
are.

Cancel is not an undo: a job that already succeeded or failed keeps its
outcome.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from hrono.db.database import tx
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
    row is not one. Its own status is derived from them and finalized
    once the last of them ends.

    A PENDING job is stopped outright. A RUNNING one is flipped too — that is
    the cooperative stop signal ``pool.running`` already polls between LLM
    calls, so a long op halts at its next checkpoint instead of running to the
    end of a multi-minute chain nobody wants anymore. Its worker thread still
    finishes the step it is on (killing a thread mid-transaction is how a
    database corrupts), which is why the report counts it as ``running``:
    told to stop, not yet stopped. The worker's terminal write is guarded on
    ``status = 'running'``, so the flip is never overwritten by the outcome.
    """
    targets = [row["id"] for row in store.children(conn, job_id)] or [job_id]
    marks = ",".join("?" * len(targets))
    now = datetime.now(UTC).isoformat()
    with tx(conn):
        cursor = conn.execute(
            "UPDATE jobs SET status = ?, updated_at = ? "  # noqa: S608
            f"WHERE id IN ({marks}) AND status = ?",
            (JobStatus.CANCELED, now, *targets, JobStatus.PENDING),
        )
        stopped = int(cursor.rowcount)
        signaled = conn.execute(
            "UPDATE jobs SET status = ?, updated_at = ? "  # noqa: S608
            f"WHERE id IN ({marks}) AND status = ?",
            (JobStatus.CANCELED, now, *targets, JobStatus.RUNNING),
        )
        running = int(signaled.rowcount)
        store.finalize_parent(conn, job_id, now)
    return Cancellation(
        stopped=stopped,
        running=running,
        finished=len(targets) - stopped - running,
    )
