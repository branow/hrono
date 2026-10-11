import json
import logging
import sqlite3
import threading
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from hrono.db.connection import connect
from hrono.db.database import Database, Pool
from hrono.jobs import store
from hrono.jobs.model import to_job
from hrono.jobs.ops import Handler, JobContext
from hrono.jobs.worker import (
    _BEAT_GRACE,
    Worker,
    enqueue,
    reclaim_stranded,
)


def database(tmp_path: Path) -> Database:
    return Database.at(tmp_path / "hrono.db")


def status_of(db: Database, job_id: str) -> str | None:
    with db.connect() as conn:
        row = store.get(conn, job_id)
    return row["status"] if row is not None else None


def wait_terminal(
    db: Database, job_id: str, timeout: float = 5.0
) -> str | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = status_of(db, job_id)
        if current in ("succeeded", "failed"):
            return current
        time.sleep(0.01)
    return status_of(db, job_id)


def run_workers(db: Database, ops: dict[str, Handler], count: int = 1) -> list:
    workers = [Worker(db, ops) for _ in range(count)]
    for worker in workers:
        worker.start()
    return workers


def stop(workers: list) -> None:
    for worker in workers:
        worker.stop()
    for worker in workers:
        worker.join(timeout=5)


def test_enqueue_runs_and_succeeds(tmp_path: Path) -> None:
    db = database(tmp_path)
    workers = run_workers(db, {"noop": lambda job, ctx: None})
    try:
        job_id = enqueue(db, "noop", {"type": "all"})
        assert wait_terminal(db, job_id) == "succeeded"
    finally:
        stop(workers)
    db.close()


def test_a_failing_leaf_fails_without_killing_siblings(tmp_path: Path) -> None:
    def boom(job: object, ctx: object) -> None:
        raise RuntimeError("kaboom")

    db = database(tmp_path)
    workers = run_workers(db, {"boom": boom, "noop": lambda job, ctx: None})
    try:
        bad = enqueue(db, "boom", {})
        good = enqueue(db, "noop", {})
        assert wait_terminal(db, bad) == "failed"
        assert wait_terminal(db, good) == "succeeded"
        with db.connect() as conn:
            row = store.get(conn, bad)
        # the record is the ENVELOPE, and the op's own wording
        # ("kaboom" — here a RuntimeError, in the field sqlite's ABORT text)
        # never becomes hrono's answer; the type is all a client learns.
        assert row["error_code"] == "internal-error"
        assert "kaboom" not in row["error"]
        assert json.loads(row["error_details"]) == {"type": "RuntimeError"}
    finally:
        stop(workers)
    db.close()


def test_each_job_runs_exactly_once_under_concurrency(tmp_path: Path) -> None:
    lock = threading.Lock()
    ran: list[str] = []

    def count(job: object, ctx: object) -> None:
        with lock:
            ran.append(job.id)  # type: ignore[attr-defined]

    db = database(tmp_path)
    ids = [enqueue(db, "count", {"i": i}) for i in range(30)]
    workers = run_workers(db, {"count": count}, count=3)
    try:
        for job_id in ids:
            assert wait_terminal(db, job_id) == "succeeded"
    finally:
        stop(workers)
    assert sorted(ran) == sorted(ids)
    assert len(ran) == 30
    db.close()


def test_a_job_dying_mid_transaction_does_not_wedge_the_queue(
    tmp_path: Path,
) -> None:
    """After a job fails inside a write, the worker must still claim jobs and
    see rows another process has committed."""

    def poison(job: object, ctx: JobContext) -> None:
        with ctx.database.write() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS probe (n INTEGER)")
            conn.execute("INSERT INTO probe (n) VALUES (1)")
            raise RuntimeError("died holding the write lock")

    db = database(tmp_path)
    workers = run_workers(db, {"poison": poison, "noop": lambda job, ctx: None})
    try:
        assert wait_terminal(db, enqueue(db, "poison", {})) == "failed"

        foreign = connect(tmp_path / "hrono.db", extensions=False)
        job_id = f"job_{uuid.uuid4().hex}"
        store.insert(foreign, job_id, None, None, "noop", "{}", _stamp())
        foreign.close()

        assert wait_terminal(db, job_id) == "succeeded"
        with db.connect() as conn:
            leftover = conn.execute(
                "SELECT name FROM sqlite_master WHERE name = 'probe'"
            ).fetchall()
        assert leftover == []  # the failed write rolled back whole
    finally:
        stop(workers)
    db.close()


class Flaky:
    """Lends connections from a real pool, refusing the next one when armed."""

    def __init__(
        self, path: Path, armed: threading.Event, refused: threading.Event
    ) -> None:
        self._pool = Pool(path)
        self._armed = armed
        self._refused = refused

    def acquire(self) -> sqlite3.Connection:
        if self._armed.is_set():
            self._armed.clear()
            self._refused.set()
            raise sqlite3.OperationalError("database is locked")
        return self._pool.acquire()

    def release(
        self, connection: sqlite3.Connection, *, reusable: bool
    ) -> None:
        self._pool.release(connection, reusable=reusable)

    def close(self) -> None:
        self._pool.close()


def wedging(tmp_path: Path) -> tuple[Database, Worker, threading.Event]:
    """A worker whose status write loses the database once."""
    armed = threading.Event()
    refused = threading.Event()
    db = Database(Flaky(tmp_path / "hrono.db", armed, refused))

    def wedge(job: object, ctx: object) -> None:
        armed.set()

    worker = Worker(
        db,
        {"wedge": wedge, "noop": lambda job, ctx: None},
        poll_interval=0.01,
        heartbeat_interval=60.0,
    )
    return db, worker, refused


def strand(db: Database, op: str, age: float) -> str:
    """Write the row a worker that died mid-job leaves behind."""
    job_id = f"job_{uuid.uuid4().hex}"
    beat = (datetime.now(UTC) - timedelta(seconds=age)).isoformat()
    with db.write() as conn:
        store.insert(conn, job_id, None, None, op, "{}", _stamp())
        conn.execute(
            "UPDATE jobs SET status = 'running', heartbeat = ? WHERE id = ?",
            (beat, job_id),
        )
    return job_id


def test_a_failing_status_write_does_not_kill_the_worker(
    tmp_path: Path,
) -> None:
    """A write in `_finish` must not escape `run()`: the thread would end and
    the job enqueued after it would never be claimed."""
    db, worker, refused = wedging(tmp_path)
    worker.start()
    try:
        wedged = enqueue(db, "wedge", {})
        assert refused.wait(5)
        assert wait_terminal(db, enqueue(db, "noop", {})) == "succeeded"
        assert worker.is_alive()
        assert status_of(db, wedged) == "running"
    finally:
        stop([worker])
    db.close()


def test_a_failing_status_write_is_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A failing status write shows up in the server log."""
    db, worker, refused = wedging(tmp_path)
    with caplog.at_level(logging.ERROR, logger="hrono.worker"):
        worker.start()
        try:
            enqueue(db, "wedge", {})
            assert refused.wait(5)
            assert wait_terminal(db, enqueue(db, "noop", {})) == "succeeded"
        finally:
            stop([worker])
    failures = [
        record
        for record in caplog.records
        if "worker cycle failed" in record.getMessage()
    ]
    assert failures
    assert all(record.exc_info is not None for record in failures)
    db.close()


def test_a_job_stranded_by_a_dead_worker_is_reclaimed_and_rerun(
    tmp_path: Path,
) -> None:
    """A job whose heartbeat stopped goes back on the queue and a later worker
    runs it — never stranded. Re-running is safe only while ops are idempotent:
    every expensive stage is keyed by content hash."""
    ran: list[str] = []
    db = database(tmp_path)
    stranded = strand(db, "count", age=5.0)
    worker = Worker(
        db,
        {"count": lambda job, ctx: ran.append(job.id)},
        poll_interval=0.01,
        heartbeat_interval=0.02,
        stale_after=0.2,
    )
    worker.start()
    try:
        assert wait_terminal(db, stranded) == "succeeded"
        assert ran == [stranded]
    finally:
        stop([worker])
    db.close()


def test_a_running_job_is_not_reclaimed_while_its_worker_beats(
    tmp_path: Path,
) -> None:
    """The heartbeat is stamped while the op runs, so a long job is never
    mistaken for a dead worker's leftovers and re-run beside itself."""
    release = threading.Event()
    ran: list[str] = []

    def slow(job: object, ctx: object) -> None:
        ran.append(job.id)  # type: ignore[attr-defined]
        release.wait(5)

    db = database(tmp_path)
    worker = Worker(
        db,
        {"slow": slow},
        poll_interval=0.01,
        heartbeat_interval=0.01,
        stale_after=0.08,
    )
    worker.start()
    try:
        job_id = enqueue(db, "slow", {})
        time.sleep(0.3)  # several times stale_after
        assert status_of(db, job_id) == "running"
        release.set()
        assert wait_terminal(db, job_id) == "succeeded"
        assert ran == [job_id]
    finally:
        release.set()
        stop([worker])
    db.close()


def test_the_startup_sweep_requeues_every_running_job(tmp_path: Path) -> None:
    """A hard crash leaves a fresh heartbeat behind; at startup no worker holds
    anything, so every running job is a leftover."""
    db = database(tmp_path)
    fresh = strand(db, "noop", age=0.0)
    assert reclaim_stranded(db) == (fresh,)
    assert status_of(db, fresh) == "pending"
    db.close()


def _stamp() -> str:
    return datetime.now(UTC).isoformat()


def _result_of(db: Database, job_id: str) -> object:
    with db.connect() as conn:
        return to_job(store.get(conn, job_id)).result


def test_an_ops_outcome_is_persisted_with_the_job(tmp_path: Path) -> None:
    # a job that succeeded incompletely must be distinguishable from a
    # clean one by reading the JOB, with no SQL against an audit table.
    db = database(tmp_path)
    workers = run_workers(
        db,
        {
            "reports": lambda job, ctx: {"judged": 2, "incomplete": True},
            "quiet": lambda job, ctx: None,
        },
    )
    try:
        loud = enqueue(db, "reports", {})
        quiet = enqueue(db, "quiet", {})
        assert wait_terminal(db, loud) == "succeeded"
        assert wait_terminal(db, quiet) == "succeeded"
    finally:
        stop(workers)

    assert _result_of(db, loud) == {"judged": 2, "incomplete": True}
    assert _result_of(db, quiet) is None  # nothing to say, nothing stored
    db.close()


def test_a_failed_job_keeps_the_error_and_reports_no_outcome(
    tmp_path: Path,
) -> None:
    def boom(job: object, ctx: object) -> None:
        raise RuntimeError("kaboom")

    db = database(tmp_path)
    workers = run_workers(db, {"boom": boom})
    try:
        bad = enqueue(db, "boom", {})
        assert wait_terminal(db, bad) == "failed"
    finally:
        stop(workers)

    assert _result_of(db, bad) is None  # an error is not an outcome
    db.close()


def test_a_reclaim_does_not_erase_a_recorded_outcome(tmp_path: Path) -> None:
    # `set_status` COALESCEs the result, so a status flip that carries no
    # outcome — a reclaim, a cancel — never wipes what the run reported.
    db = database(tmp_path)
    job_id = enqueue(db, "noop", {})
    with db.connect() as conn:
        store.set_status(conn, job_id, "succeeded", None, "t", '{"judged": 1}')
        store.set_status(conn, job_id, "pending", None, "t")

    assert _result_of(db, job_id) == {"judged": 1}
    db.close()


def wait_healthy(worker: Worker, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if worker.healthy():
            return True
        time.sleep(0.01)
    return False


def test_a_worker_with_both_threads_running_is_healthy(tmp_path: Path) -> None:
    db = database(tmp_path)
    workers = run_workers(db, {"noop": lambda job, ctx: None})
    try:
        assert wait_healthy(workers[0])  # idle, holding no job: still healthy
    finally:
        stop(workers)
    assert not workers[0].healthy()  # stopped: not healthy
    db.close()


def test_a_dead_reclaimer_makes_the_worker_unhealthy(tmp_path: Path) -> None:
    # `is_alive()` reports the SUPERVISOR. If the reclaimer thread ended
    # while the supervisor lived, nothing would requeue a stranded job and
    # /health would still answer alive.
    db = database(tmp_path)
    workers = run_workers(db, {"noop": lambda job, ctx: None})
    try:
        worker = workers[0]
        assert wait_healthy(worker)
        worker._beat_thread = threading.Thread(target=lambda: None)  # never run
        assert worker.is_alive()  # the supervisor is untouched
        assert not worker.healthy()  # the reclaimer is not
    finally:
        stop(workers)
    db.close()


def test_a_wedged_reclaimer_makes_the_worker_unhealthy(tmp_path: Path) -> None:
    # a beat whose thread lives but has stopped coming round is as bad as a
    # dead one: nothing is being stamped or swept either way.
    db = database(tmp_path)
    workers = run_workers(db, {"noop": lambda job, ctx: None})
    try:
        worker = workers[0]
        assert wait_healthy(worker)
        worker._last_beat -= 10 * worker._heartbeat_interval
        assert not worker.healthy()
    finally:
        stop(workers)
    db.close()


def test_a_worker_running_a_long_job_stays_healthy(tmp_path: Path) -> None:
    # the beat runs BESIDE the loop, so a job that takes a while must not make
    # the worker look dead — the whole point of stamping from a second thread.
    started, release = threading.Event(), threading.Event()

    def slow(job: object, ctx: object) -> None:
        started.set()
        release.wait(timeout=5)

    db = database(tmp_path)
    workers = run_workers(db, {"slow": slow})
    try:
        assert wait_healthy(workers[0])
        enqueue(db, "slow", {})
        assert started.wait(timeout=5)
        assert workers[0].healthy()  # mid-execution
    finally:
        release.set()
        stop(workers)
    db.close()


def test_health_depends_on_the_beat_actually_coming_round(
    tmp_path: Path,
) -> None:
    # the stamp is what makes a WEDGED beat detectable, so it has to be proven
    # to happen: a worker left running past several grace windows stays healthy
    # only because its beat keeps arriving.
    db = database(tmp_path)
    worker = Worker(
        db, {"noop": lambda job, ctx: None}, heartbeat_interval=0.02
    )
    worker.start()
    try:
        assert wait_healthy(worker)
        time.sleep(_BEAT_GRACE * 0.02 * 3)  # three grace windows
        assert worker.healthy()
    finally:
        worker.stop()
        worker.join(timeout=5)
    db.close()


def test_a_dead_supervisor_makes_the_worker_unhealthy(tmp_path: Path) -> None:
    # the mirror of the dead-reclaimer case. Every other unhealthy path gets
    # there by stopping the worker, which ends BOTH threads — so the supervisor
    # branch was never the reason any test failed, and deleting it left the
    # suite green. A worker whose supervisor ended claims and executes nothing.
    db = database(tmp_path)
    worker = Worker(
        db, {"noop": lambda job, ctx: None}, heartbeat_interval=0.02
    )
    worker.start()
    try:
        assert wait_healthy(worker)
    finally:
        worker.stop()
        worker.join(timeout=5)

    release = threading.Event()
    beating = threading.Thread(target=release.wait, daemon=True)
    beating.start()
    worker._beat_thread = beating  # a reclaimer that is still going
    worker._last_beat = time.monotonic()  # ... and beating right now
    try:
        assert not worker.is_alive()  # only the supervisor is gone
        assert not worker.healthy()
    finally:
        release.set()
        beating.join(timeout=3)
    db.close()
