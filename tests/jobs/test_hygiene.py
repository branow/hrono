"""The jobs table's hygiene: idle cost, crash loops, retention, transactions.

Each test here guards one failure mode: the idle worker taking the write
lock dozens of times a second, a poison-pill job retried forever,
fan-out parents and finished runs accumulating for the life of the database,
and a store call committing its caller's transaction out from under it.
"""

from __future__ import annotations

import time
from pathlib import Path

from hrono.db.database import Database
from hrono.jobs import store
from hrono.jobs.worker import Worker, enqueue


class Spy:
    """A Database that counts how often each door is opened."""

    def __init__(self, inner: Database) -> None:
        self._inner = inner
        self.writes = 0
        self.reads = 0

    def connect(self):  # noqa: ANN201
        self.reads += 1
        return self._inner.connect()

    def write(self):  # noqa: ANN201
        self.writes += 1
        return self._inner.write()

    def close(self) -> None:
        self._inner.close()


def test_an_idle_worker_never_takes_the_write_lock(tmp_path: Path) -> None:
    """The claim polls through the READ door until something is pending.

    At a 20 ms poll the old claim-by-write held ``BEGIN IMMEDIATE`` about 50
    times a second on an idle server, and every HTTP writer competed with a
    loop that had nothing to do.
    """
    spy = Spy(Database.at(tmp_path / "hrono.db"))
    worker = Worker(spy, {}, poll_interval=0.01, heartbeat_interval=60.0)
    worker.start()
    try:
        time.sleep(0.2)
        assert spy.reads > 3  # it really was polling
        assert spy.writes == 0  # ... without ever taking the write lock
    finally:
        worker.stop()
        worker.join(timeout=5)
        spy.close()


def test_a_job_that_strands_repeatedly_is_failed_not_requeued(
    tmp_path: Path,
) -> None:
    # a job that takes its worker down comes back 'running' with a dead
    # heartbeat after every restart; without a cap it was retried forever.
    db = Database.at(tmp_path / "hrono.db")
    try:
        job_id = enqueue(db, "noop", {})
        with db.write() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'running', attempts = ? WHERE id = ?",
                (store.MAX_ATTEMPTS, job_id),
            )
            requeued, looping = store.reclaim(conn, None, "t")
        assert requeued == ()
        assert looping == (job_id,)
        with db.connect() as conn:
            row = store.get(conn, job_id)
        assert row is not None
        assert row["status"] == "failed"
        assert row["error_code"] == "crash-loop"
    finally:
        db.close()


def test_a_stranded_job_below_the_cap_is_requeued_and_counted(
    tmp_path: Path,
) -> None:
    db = Database.at(tmp_path / "hrono.db")
    try:
        job_id = enqueue(db, "noop", {})
        with db.write() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'running' WHERE id = ?", (job_id,)
            )
            requeued, looping = store.reclaim(conn, None, "t")
        assert requeued == (job_id,)
        assert looping == ()
        with db.connect() as conn:
            row = conn.execute(
                "SELECT status, attempts FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        assert row is not None
        assert row["status"] == "pending"
        assert int(row["attempts"]) == 1
    finally:
        db.close()


def test_prune_sweeps_old_terminal_runs_and_keeps_the_rest(
    tmp_path: Path,
) -> None:
    db = Database.at(tmp_path / "hrono.db")
    try:
        old_root = enqueue(db, "noop", {})
        old_child = enqueue(db, "noop", {}, parent_id=old_root)
        live = enqueue(db, "noop", {})
        fresh = enqueue(db, "noop", {})
        with db.write() as conn:
            conn.execute(
                "UPDATE jobs SET status = 'succeeded', "
                "updated_at = '2020-01-01T00:00:00' WHERE id IN (?, ?)",
                (old_root, old_child),
            )
            conn.execute(
                "UPDATE jobs SET status = 'succeeded' WHERE id = ?", (fresh,)
            )
            removed = store.prune(conn, "2025-01-01T00:00:00")
        assert removed == 2
        with db.connect() as conn:
            kept = {
                row["id"]
                for row in conn.execute("SELECT id FROM jobs").fetchall()
            }
        assert kept == {live, fresh}  # running and recent rows survive
    finally:
        db.close()


def test_a_store_call_does_not_commit_its_callers_transaction(
    tmp_path: Path,
) -> None:
    """`tx` joins an open transaction instead of committing it.

    ``with conn:`` commits whatever is open on exit, so a store call inside
    ``Database.write()`` released the write lock in the middle of a block
    that promises one transaction — the hole that made ``rotate_running``'s
    "rekey under the same lock" false.
    """
    db = Database.at(tmp_path / "hrono.db")
    try:
        with db.write() as conn:
            store.insert(conn, "job_x", None, None, "noop", "{}", "t")
            assert conn.in_transaction  # the caller's transaction survives
            store.set_status(conn, "job_x", "succeeded", None, "t")
            assert conn.in_transaction
    finally:
        db.close()


def test_prune_also_sweeps_old_update_log_rows(tmp_path: Path) -> None:
    from hrono.db import update_log

    db = Database.at(tmp_path / "hrono.db")
    try:
        with db.write() as conn:
            update_log.record(conn, "default", 1, "drain", "core")
            conn.execute(
                "UPDATE update_log SET created_at = '2020-01-01T00:00:00'"
            )
            update_log.record(conn, "default", 2, "drain", "core")
            removed = update_log.prune(conn, "2025-01-01T00:00:00")
        assert removed == 1
        with db.connect() as conn:
            left = conn.execute("SELECT COUNT(*) FROM update_log").fetchone()[0]
        assert int(left) == 1  # the recent decision survives
    finally:
        db.close()
