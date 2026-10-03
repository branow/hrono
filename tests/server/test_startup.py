import time
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hrono.crypto.masterkey import WrongMasterKey, reconcile
from hrono.db.connection import connect
from hrono.db.database import open_database
from hrono.db.migrations import packaged
from hrono.errors import Internal
from hrono.jobs import store
from hrono.jobs.ops import JobContext
from hrono.server.app import create_app

KEY = Fernet.generate_key()


def _probe_route(app: FastAPI) -> None:
    @app.post("/_probe")
    def probe() -> dict[str, int]:
        with app.state.db.connect() as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS probe (n INTEGER)")
            with conn:
                conn.execute("INSERT INTO probe (n) VALUES (1)")
            count = conn.execute("SELECT count(*) FROM probe").fetchone()[0]
        return {"count": count}


def test_startup_creates_db_and_applies_migrations(tmp_path: Path) -> None:
    db = tmp_path / "hrono.db"
    with TestClient(create_app(db_path=db, master_key=KEY)):
        pass
    assert db.exists()
    conn = connect(db, extensions=False)
    applied = {
        row["version"]
        for row in conn.execute("SELECT version FROM schema_migrations")
    }
    assert applied == {m.version for m in packaged()}
    assert conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='keys'"
    ).fetchone()
    conn.close()


def test_repeat_startup_applies_nothing(tmp_path: Path) -> None:
    db = tmp_path / "hrono.db"
    with TestClient(create_app(db_path=db, master_key=KEY)):
        pass
    with TestClient(create_app(db_path=db, master_key=KEY)):
        pass
    conn = connect(db, extensions=False)
    count = conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    assert count == len(packaged())
    conn.close()


def test_health_ok_after_startup_wiring(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "hrono.db", master_key=KEY)
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200


def test_injected_connection_is_used_and_left_open(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app), app.state.db.connect() as active:
        assert active is conn
    assert conn.execute("SELECT 1").fetchone()[0] == 1
    conn.close()


def test_sync_handler_uses_db_through_testclient(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "hrono.db", master_key=KEY)
    _probe_route(app)
    with TestClient(app) as client:
        response = client.post("/_probe")
        assert response.status_code == 200
        assert response.json()["count"] == 1


def test_startup_tags_secrets_with_the_reconciled_key_id(
    tmp_path: Path,
) -> None:
    app = create_app(db_path=tmp_path / "hrono.db", master_key=KEY)
    with TestClient(app):
        assert app.state.cipher.encrypt("x").key_id == 1


def test_startup_refuses_a_wrong_master_key(tmp_path: Path) -> None:
    db = tmp_path / "hrono.db"
    with TestClient(create_app(db_path=db, master_key=KEY)):
        pass
    other = Fernet.generate_key()
    with pytest.raises(WrongMasterKey):  # noqa: SIM117
        with TestClient(create_app(db_path=db, master_key=other)):
            pass


def test_startup_requeues_and_runs_a_job_left_running(tmp_path: Path) -> None:
    """F24: a job whose worker died stayed `running` for ever, and the jobs
    enqueued after it were never claimed."""
    path = tmp_path / "hrono.db"
    conn = open_database(path)
    stamp = datetime.now(UTC).isoformat()
    store.insert(conn, "job_stranded", None, None, "noop", "{}", stamp)
    conn.execute(
        "UPDATE jobs SET status = 'running', heartbeat = ? WHERE id = ?",
        (stamp, "job_stranded"),
    )
    conn.commit()
    conn.close()

    reader = connect(path, extensions=False)
    with TestClient(create_app(db_path=path, master_key=KEY)):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            status = store.get(reader, "job_stranded")["status"]
            if status == "succeeded":
                break
            time.sleep(0.01)
    assert store.get(reader, "job_stranded")["status"] == "succeeded"
    reader.close()


def test_an_injected_connection_app_has_no_cache_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # #119/#098: the last route by which a cwd-relative cache could reach a
    # worker. An app built from an injected connection does not own a database
    # PATH, so it must hand its ops no cache root at all rather than resolve
    # one against the working directory — F25 was two divergent clone sets for
    # one database, and a diff that invented a reversed rename.
    monkeypatch.chdir(tmp_path)
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    app = create_app(connection=conn, master_key=KEY, key_id=1)

    with TestClient(app):
        context = JobContext(app.state.db, None, app.state.worker._cache_root)
        with pytest.raises(Internal, match="no cache root"):
            context.cache_for("repo")

    assert not (tmp_path / ".hrono").exists()  # nothing resolved against cwd
    conn.close()
