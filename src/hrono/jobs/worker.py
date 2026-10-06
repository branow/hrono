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
import time
import uuid
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
from hrono.errors import AppError, BadRequest, Internal, as_app_error
from hrono.jobs import store
from hrono.jobs.model import (
    Job,
    serialize_result,
    serialize_scope,
    to_job,
)
from hrono.jobs.ops import OPS, Handler, JobContext
from hrono.jobs.stages import StageFailed

HEARTBEAT_INTERVAL = 5.0
_BEAT_GRACE = 4  # missed beats before the reclaimer counts as gone (#111)

STALE_AFTER = 60.0

_PRUNE_INTERVAL = 3600.0  # the retention sweep runs at most once an hour

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
    started_by: str | None = None,
) -> str:
    """Insert a pending job and return its id (ops/endpoints call this).

    ``started_by`` is the user whose request this is (#201); a child names no
    one of its own and takes its parent's, so a run's calls add up under the
    person who started it.
    """
    job_id = f"job_{uuid.uuid4().hex}"
    now = _now()
    with database.write() as conn:
        if parent_id is not None and started_by is None:
            parent = store.get(conn, parent_id)
            started_by = None if parent is None else parent["started_by"]
        store.insert(
            conn,
            job_id,
            parent_id,
            tree,
            op,
            serialize_scope(scope),
            now,
            started_by,
        )
    return job_id


def reclaim_stranded(database: Database) -> tuple[str, ...]:
    """Requeue every job left ``running`` by a worker that is gone.

    Called at startup, before any worker runs, so a job whose worker died with
    the process is re-run rather than stranded for ever (F24). A job that has
    taken its worker down ``MAX_ATTEMPTS`` times is failed instead of requeued:
    re-running a poison pill on every restart is a crash loop nobody sees.
    """
    with database.write() as conn:
        requeued, looping = store.reclaim(conn, None, _now())
    for job_id in requeued:
        _logger.warning(
            "requeued job left running by a dead worker: %s", job_id
        )
    for job_id in looping:
        _logger.error("failed crash-looping job: %s", job_id)
    return requeued


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
        self._last_prune = 0.0
        self._stopped = threading.Event()
        self._beat_thread = threading.Thread(target=self._beat, daemon=True)
        self._last_beat = time.monotonic()

    def run(self) -> None:
        beat = self._beat_thread
        beat.start()
        try:
            self._supervise()
        finally:
            beat.join(timeout=5)

    def healthy(self) -> bool:
        """True when BOTH of this worker's threads are doing their job (#111).

        ``is_alive()`` reports the supervisor, which claims and executes; the
        reclaimer that stamps heartbeats and requeues stranded jobs is a second
        thread, and if it ended while the supervisor lived nothing would recover
        a stranded job while ``/health`` still answered ``alive`` — a quieter
        replay of the failure #092's health check exists to catch.

        A worker that has started but whose beat has not begun answers False —
        starting is not yet healthy, which is the honest answer for a readiness
        probe and the one that keeps a half-up server out of rotation.

        Derived from an IN-MEMORY stamp rather than ``jobs.heartbeat``: health
        is unauthenticated and may be polled hard, so it must add no query, and
        an idle worker holds no job to stamp a row with. A beat that has not
        come round within ``_BEAT_GRACE`` intervals is treated as gone even if
        its thread is technically alive, which covers a wedged beat as well as a
        dead one.
        """
        if not self.is_alive():
            return False
        if not self._beat_thread.is_alive():
            return False
        grace = _BEAT_GRACE * self._heartbeat_interval
        return time.monotonic() - self._last_beat <= grace

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
                requeued = self._sweep()
                self._prune()
            except Exception as exc:  # noqa: BLE001 - the beat must outlive it
                _logger.warning("heartbeat failed: %s", exc)
                continue
            self._last_beat = time.monotonic()
            for job_id in requeued:
                _logger.warning("requeued stranded job: %s", job_id)

    def _sweep(self) -> tuple[str, ...]:
        held = self._held
        with self._database.write() as conn:
            if held is not None:
                store.touch(conn, held, _now())
            requeued, looping = store.reclaim(
                conn, _cutoff(self._stale_after), _now()
            )
        for job_id in looping:
            _logger.error("failed crash-looping job: %s", job_id)
        return requeued

    def _prune(self) -> None:
        """Sweep old terminal runs, at most once an hour.

        Nothing else ever deletes a job row, so without this the table — and
        the claim scan, the runs CTE and every listing — grows forever.
        """
        if time.monotonic() - self._last_prune < _PRUNE_INTERVAL:
            return
        self._last_prune = time.monotonic()
        cutoff = (
            datetime.now(UTC) - timedelta(days=store.JOB_RETENTION_DAYS)
        ).isoformat()
        with self._database.write() as conn:
            removed = store.prune(conn, cutoff)
        if removed:
            _logger.info("pruned %d finished job rows", removed)

    def _claim(self) -> Job | None:
        # a read-door peek first: an idle worker must not take the write lock
        # dozens of times a second just to learn there is nothing to do.
        with self._database.connect() as conn:
            waiting = store.has_runnable(conn)
        if not waiting:
            return None
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
                # the op name came from the client's own request, so it is
                # safe to say back — and useless to hide behind "the job
                # failed" (#109).
                raise BadRequest(f"unknown op: {job.op}")
            outcome = handler(
                job,
                JobContext(
                    self._database, self._cipher, self._cache_root, job.id
                ),
            )
        except Exception as exc:  # noqa: BLE001 - a leaf failure is recorded
            # the record keeps the CODE; the driver's own wording lives here,
            # where an operator can read it and a client cannot (#109).
            _logger.exception("job %s (%s) failed", job.id, job.op)
            # a composite op's failure carries the stages it DID finish (#213)
            self._finish(job, "failed", exc, getattr(exc, "outcome", None))
        else:
            self._finish(job, "succeeded", None, outcome)
        finally:
            self._held = None

    def _finish(
        self,
        job: Job,
        status: str,
        error: BaseException | None,
        outcome: object = None,
    ) -> None:
        """Record the terminal status, the failure's CODE, and the op's counts.

        An op that returns nothing persists nothing (#132): most ops have no
        outcome worth a reader's time, and a null column says exactly that.

        A failure is recorded in the envelope every other surface answers in
        (#109): a kebab-case code, a client-safe message, and details. The
        exception is mapped through ``as_app_error`` first, so a job never
        records the driver's phrasing as hrono's answer.
        """
        result = (
            serialize_result(outcome) if isinstance(outcome, Mapping) else None
        )
        mapped = _mapped(error) if error is not None else None
        with self._database.write() as conn:
            store.set_status(
                conn,
                job.id,
                status,
                mapped.message if mapped else None,
                _now(),
                result,
                code=mapped.code if mapped else None,
                details=serialize_result(mapped.details if mapped else None),
                # only over 'running': a cancel (or a reclaim) that moved the
                # row first must not be overwritten by this thread's outcome.
                expected="running",
            )
            if job.parent_id is not None:
                store.finalize_parent(conn, job.parent_id, _now())


def _mapped(error: BaseException) -> AppError:
    """The failure as hrono's envelope; a stage's failure names the stage.

    The code is the CAUSE's — ``llm-error``, not "a stage failed" — and the
    stage and the item it was on go into the details beside it (#213).
    """
    if not isinstance(error, StageFailed):
        return as_app_error(error)
    cause = as_app_error(error.cause)
    return Internal(
        cause.message,
        code=cause.code,
        details={
            **(cause.details or {}),
            "stage": error.stage,
            "item": error.item,
        },
    )


def _backoff(failures: int) -> float:
    return min(_RESTART_BACKOFF_CAP, _RESTART_BACKOFF * 2 ** (failures - 1))


def _cutoff(stale_after: float) -> str:
    return (datetime.now(UTC) - timedelta(seconds=stale_after)).isoformat()


def _now() -> str:
    return datetime.now(UTC).isoformat()
