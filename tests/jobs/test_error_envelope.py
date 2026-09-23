"""#109: a job's failure carries a CODE, not the driver's wording.

092 mapped *busy* driver errors onto `Unavailable`; every other driver error
still reached the record as `str(exc)`. The reproduction in the ticket is here
verbatim — a `BEFORE INSERT` trigger raising `RAISE(ABORT, ...)` inside an op —
and it must not put sqlite's phrasing in hrono's mouth.
"""

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.errors import Conflict
from hrono.jobs import store
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.jobs.worker import Worker, enqueue
from hrono.server.app import create_app

KEY = Fernet.generate_key()
POISON = "poisoned mid-transaction"


def _wait(db: Database, job_id: str, timeout: float = 5.0) -> sqlite3.Row:
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with db.connect() as conn:
            row = store.get(conn, job_id)
        if row is not None and row["status"] in ("succeeded", "failed"):
            return row
        time.sleep(0.01)
    raise AssertionError(f"job {job_id} never finished")


def _driver_error(job: Job, context: JobContext) -> None:
    """The ticket's reproduction: sqlite aborts mid-op, in its own words."""
    with context.database.write() as conn:
        conn.execute(
            "CREATE TRIGGER IF NOT EXISTS poison BEFORE INSERT ON node_members "
            f"BEGIN SELECT RAISE(ABORT, '{POISON}'); END"
        )
        conn.execute(
            "INSERT INTO nodes(id, tree, level, label, created_at) "
            "VALUES (1, 'default', 0, 0, 't')"
        )
        conn.execute(
            "INSERT INTO node_members"
            "(node_id, section_id, attached, created_at) "
            "VALUES (1, 1, 0, 't')"
        )


def _app_error(job: Job, context: JobContext) -> None:
    raise Conflict("a reshaping job holds the tree", details={"tree": "x"})


def _run(db: Database, op: str, handler: object) -> sqlite3.Row:
    worker = Worker(db, {op: handler})  # type: ignore[arg-type]
    worker.start()
    try:
        return _wait(db, enqueue(db, op, {}))
    finally:
        worker.stop()
        worker.join(timeout=5)


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    yield database
    database.close()


def test_a_driver_error_is_recorded_as_a_code_not_sqlites_wording(
    db: Database,
) -> None:
    row = _run(db, "poison", _driver_error)

    assert row["status"] == "failed"
    assert row["error_code"] == "internal-error"
    # the wording the ticket caught being served as hrono's answer
    assert POISON not in (row["error"] or "")
    assert POISON not in json.dumps(row["error_details"])
    assert row["error"] == "the job failed"
    assert json.loads(row["error_details"]) == {"type": "IntegrityError"}


def test_the_drivers_wording_reaches_the_log_and_only_the_log(
    db: Database, caplog: pytest.LogCaptureFixture
) -> None:
    # hiding the wording from the client must not hide it from the operator:
    # before #109 `str(exc)` was at least ON the record, so a log line is what
    # keeps the failure diagnosable at all. It also proves the trigger really
    # fired — a fixture that failed on some other constraint would satisfy
    # every "the wording is absent" assertion below while testing nothing.
    with caplog.at_level("ERROR", logger="hrono.worker"):
        row = _run(db, "poison", _driver_error)

    assert POISON in caplog.text
    assert POISON not in (row["error"] or "")


def test_an_unknown_op_says_which_op(db: Database) -> None:
    # the op name came from the client's own request: safe to say back, and
    # useless as "the job failed".
    worker = Worker(db, {})
    worker.start()
    try:
        row = _wait(db, enqueue(db, "no-such-op", {}))
    finally:
        worker.stop()
        worker.join(timeout=5)

    assert row["error_code"] == "bad-request"
    assert row["error"] == "unknown op: no-such-op"


def test_hronos_own_wording_survives(db: Database) -> None:
    # the other side of the rule: an error raised from hrono's own code was
    # written for a reader, and hiding it behind "the job failed" would cost
    # the operator every actionable message the system has (a missing model,
    # an unreachable source) to protect them from sqlite's phrasing.
    from hrono.ingest.sync import SyncError

    def op(job: Job, context: JobContext) -> None:
        raise SyncError("no text model is registered for this tree")

    row = _run(db, "ours", op)

    assert row["error_code"] == "sync-error"  # its own code (#145)
    assert row["error"] == "no text model is registered for this tree"
    assert json.loads(row["error_details"]) == {"type": "SyncError"}


def test_an_op_raising_an_app_error_keeps_its_own_code(db: Database) -> None:
    # the other half: an error that already IS ours passes through intact,
    # message and details included, so a client can act on the distinction.
    row = _run(db, "conflict", _app_error)

    assert row["error_code"] == "conflict"
    assert row["error"] == "a reshaping job holds the tree"
    assert json.loads(row["error_details"]) == {"tree": "x"}


def test_the_api_serves_a_failure_in_the_http_error_envelope(
    tmp_path: Path,
) -> None:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "reader", "reader")[1]
    store.insert(conn, "job_x", None, None, "split", '{"type":"all"}', "t")
    store.set_status(
        conn,
        "job_x",
        "failed",
        "the job failed",
        "t",
        code="internal-error",
        details='{"type": "IntegrityError"}',
    )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        headers = {"Authorization": f"Bearer {token}"}
        one = client.get("/jobs/job_x", headers=headers).json()
        listed = client.get("/jobs", headers=headers).json()

    envelope = {
        "code": "internal-error",
        "message": "the job failed",
        "details": {"type": "IntegrityError"},
    }
    assert one["error"] == envelope
    # the LIST serves the same shape as the fetch — a client parses one thing
    assert [j["error"] for j in listed if j["id"] == "job_x"] == [envelope]

    # and the shape is the HTTP envelope's own, field for field
    denied = client.get("/jobs/job_x").json()
    assert set(denied["error"]) == set(envelope)
    conn.close()


def test_a_succeeded_job_carries_no_error_at_all(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "reader", "reader")[1]
    store.insert(conn, "job_ok", None, None, "sync", '{"type":"all"}', "t")
    store.set_status(conn, "job_ok", "succeeded", None, "t")
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        body = client.get(
            "/jobs/job_ok", headers={"Authorization": f"Bearer {token}"}
        ).json()
    assert body["error"] is None
    conn.close()
