"""Enqueue and the background worker that runs one leaf at a time.

The worker is a daemon thread so its sync SQLite work stays off the event loop.
It polls for a pending job, claims it under the ``Database`` lock (no
double-claim), dispatches to the registered op, and records the outcome; a
failed leaf is marked ``failed`` with its reason and never stops the rest of the
queue.
"""

from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime

from hrono.db.database import Database
from hrono.jobs import store
from hrono.jobs.model import Job, serialize_scope, to_job
from hrono.jobs.ops import OPS, Handler, JobContext


def enqueue(
    database: Database,
    op: str,
    scope: dict[str, object],
    *,
    tree: str | None = None,
    parent_id: str | None = None,
) -> str:
    """Insert a pending job and return its id (ops/endpoints call this)."""
    job_id = f"job_{uuid.uuid4().hex}"
    now = _now()
    with database.connect() as conn:
        store.insert(
            conn, job_id, parent_id, tree, op, serialize_scope(scope), now
        )
    return job_id


class Worker(threading.Thread):
    """Polls pending jobs and runs each once through the op registry."""

    def __init__(
        self,
        database: Database,
        ops: dict[str, Handler] | None = None,
        *,
        poll_interval: float = 0.02,
    ) -> None:
        super().__init__(daemon=True)
        self._database = database
        self._ops = ops if ops is not None else OPS
        self._interval = poll_interval
        self._stopped = threading.Event()

    def run(self) -> None:
        while not self._stopped.is_set():
            job = self._claim()
            if job is None:
                self._stopped.wait(self._interval)
                continue
            self._execute(job)

    def stop(self) -> None:
        self._stopped.set()

    def _claim(self) -> Job | None:
        with self._database.connect() as conn:
            row = store.claim_next(conn, _now())
        return to_job(row) if row is not None else None

    def _execute(self, job: Job) -> None:
        handler = self._ops.get(job.op)
        try:
            if handler is None:
                raise LookupError(f"unknown op: {job.op}")
            handler(job, JobContext(self._database))
        except Exception as exc:  # noqa: BLE001 - a leaf failure is recorded
            self._finish(job, "failed", str(exc))
        else:
            self._finish(job, "succeeded", None)

    def _finish(self, job: Job, status: str, error: str | None) -> None:
        with self._database.connect() as conn:
            store.set_status(conn, job.id, status, error, _now())


def _now() -> str:
    return datetime.now(UTC).isoformat()
