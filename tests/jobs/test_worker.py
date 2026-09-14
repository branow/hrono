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
from hrono.jobs.ops import Handler, JobContext
from hrono.jobs.worker import Worker, enqueue, reclaim_stranded


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
            assert "kaboom" in store.get(conn, bad)["error"]
    finally:
        stop(workers)
    db.close()


def test_unknown_op_fails(tmp_path: Path) -> None:
    db = database(tmp_path)
    workers = run_workers(db, {})
    try:
        job_id = enqueue(db, "missing", {})
        assert wait_terminal(db, job_id) == "failed"
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
    """F23: after a job failed inside a write, the worker stopped claiming
    anything and never saw rows another process had committed."""

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
    """A worker whose status write loses the database once, as in F24."""
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
    """F24: the write in `_finish` escaped `run()`, the thread ended, and the
    job enqueued after it was never claimed."""
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
    """F24: `grep "Exception in thread"` on the server log found nothing."""
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
        heartbeat_interval=0.02,
        stale_after=0.15,
    )
    worker.start()
    try:
        job_id = enqueue(db, "slow", {})
        time.sleep(0.6)
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
