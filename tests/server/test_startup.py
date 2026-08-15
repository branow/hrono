from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hrono.crypto.masterkey import WrongMasterKey
from hrono.db.connection import connect
from hrono.db.database import open_database
from hrono.db.migrations import packaged
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


def test_startup_exposes_master_key_and_key_id(tmp_path: Path) -> None:
    app = create_app(db_path=tmp_path / "hrono.db", master_key=KEY)
    with TestClient(app):
        assert app.state.master_key == KEY
        assert app.state.key_id == 1


def test_startup_refuses_a_wrong_master_key(tmp_path: Path) -> None:
    db = tmp_path / "hrono.db"
    with TestClient(create_app(db_path=db, master_key=KEY)):
        pass
    other = Fernet.generate_key()
    with pytest.raises(WrongMasterKey):  # noqa: SIM117
        with TestClient(create_app(db_path=db, master_key=other)):
            pass
