"""Enqueue and the background worker that runs one leaf at a time.

The worker is a daemon thread so its sync SQLite work stays off the event loop.
It polls for a pending job, claims it under the ``Database`` lock (no
double-claim), dispatches to the registered op, and records the outcome; a
failed leaf is marked ``failed`` with its reason and never stops the rest of the
queue.

The loop supervises itself: a cycle that raises — the claim or the status write
losing the database to a foreign writer past the retry budget — is logged and
restarted under bounded backoff instead of ending the thread silently (F24). A
job whose worker stops stamping its heartbeat goes back on the queue, and so
does every running job at startup; re-running one is safe because the expensive
stages are content-hash cached.
"""

from __future__ import annotations

import logging
import threading
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
from hrono.jobs import store
from hrono.jobs.model import Job, serialize_scope, to_job
from hrono.jobs.ops import OPS, Handler, JobContext

HEARTBEAT_INTERVAL = 5.0

STALE_AFTER = 60.0

_RESTART_BACKOFF = 0.5

_RESTART_BACKOFF_CAP = 5.0

_logger = logging.getLogger("hrono.worker")


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
    with database.write() as conn:
        store.insert(
            conn, job_id, parent_id, tree, op, serialize_scope(scope), now
        )
    return job_id


def reclaim_stranded(database: Database) -> tuple[str, ...]:
    """Requeue every job left ``running`` by a worker that is gone.

    Called at startup, before any worker runs, so a job whose worker died with
    the process is re-run rather than stranded for ever (F24).
    """
    with database.write() as conn:
        reclaimed = store.reclaim(conn, None, _now())
    for job_id in reclaimed:
        _logger.warning(
            "requeued job left running by a dead worker: %s", job_id
        )
    return reclaimed


class Worker(threading.Thread):
    """Polls pending jobs and runs each once through the op registry."""

    def __init__(
        self,
        database: Database,
        ops: dict[str, Handler] | None = None,
        *,
        cipher: Cipher | None = None,
        cache_root: Path | None = None,
        poll_interval: float = 0.02,
        heartbeat_interval: float = HEARTBEAT_INTERVAL,
        stale_after: float = STALE_AFTER,
    ) -> None:
        super().__init__(daemon=True)
        self._database = database
        self._ops = ops if ops is not None else OPS
        self._cipher = cipher
        self._cache_root = cache_root
        self._interval = poll_interval
        self._heartbeat_interval = heartbeat_interval
        self._stale_after = stale_after
        self._held: str | None = None
        self._stopped = threading.Event()

    def run(self) -> None:
        beat = threading.Thread(target=self._beat, daemon=True)
        beat.start()
        try:
            self._supervise()
        finally:
            beat.join(timeout=5)

    def stop(self) -> None:
        self._stopped.set()

    def _supervise(self) -> None:
        """Run cycles until stopped, surviving a cycle that raises.

        The write inside a cycle used to escape ``run()`` and end the thread
        with no log line, leaving the claimed job running for ever and every
        later job unclaimed (F24).
        """
        failures = 0
        while not self._stopped.is_set():
            try:
                self._cycle()
            except Exception as exc:  # noqa: BLE001 - the loop must outlive it
                failures += 1
                _logger.error(
                    "worker cycle failed, restarting (%d in a row)",
                    failures,
                    exc_info=exc,
                )
                self._stopped.wait(_backoff(failures))
            else:
                failures = 0

    def _cycle(self) -> None:
        job = self._claim()
        if job is None:
            self._stopped.wait(self._interval)
            return
        self._execute(job)

    def _beat(self) -> None:
        """Keep this worker's job fresh, and requeue anyone's stale job.

        Runs beside the loop so a job stays stamped while its op executes: only
        a worker that is really gone lets its heartbeat go stale.
        """
        while not self._stopped.wait(self._heartbeat_interval):
            try:
                reclaimed = self._sweep()
            except Exception as exc:  # noqa: BLE001 - the beat must outlive it
                _logger.warning("heartbeat failed: %s", exc)
                continue
            for job_id in reclaimed:
                _logger.warning("requeued stranded job: %s", job_id)

    def _sweep(self) -> tuple[str, ...]:
        held = self._held
        with self._database.write() as conn:
            if held is not None:
                store.touch(conn, held, _now())
            return store.reclaim(conn, _cutoff(self._stale_after), _now())

    def _claim(self) -> Job | None:
        with self._database.write() as conn:
            row = store.claim_next(conn, _now())
        if row is None:
            return None
        self._held = row["id"]
        return to_job(row)

    def _execute(self, job: Job) -> None:
        handler = self._ops.get(job.op)
        try:
            if handler is None:
                raise LookupError(f"unknown op: {job.op}")
            handler(
                job,
                JobContext(self._database, self._cipher, self._cache_root),
            )
        except Exception as exc:  # noqa: BLE001 - a leaf failure is recorded
            self._finish(job, "failed", str(exc))
        else:
            self._finish(job, "succeeded", None)
        finally:
            self._held = None

    def _finish(self, job: Job, status: str, error: str | None) -> None:
        with self._database.write() as conn:
            store.set_status(conn, job.id, status, error, _now())


def _backoff(failures: int) -> float:
    return min(_RESTART_BACKOFF_CAP, _RESTART_BACKOFF * 2 ** (failures - 1))


def _cutoff(stale_after: float) -> str:
    return (datetime.now(UTC) - timedelta(seconds=stale_after)).isoformat()


def _now() -> str:
    return datetime.now(UTC).isoformat()
