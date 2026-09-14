import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from hrono.db.connection import connect
from hrono.db.database import Database
from hrono.jobs import store
from hrono.jobs.ops import Handler, JobContext
from hrono.jobs.worker import Worker, enqueue


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


def _stamp() -> str:
    return datetime.now(UTC).isoformat()
