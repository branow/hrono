from pathlib import Path

from fastapi.testclient import TestClient

from hrono.db.connection import connect
from hrono.db.database import open_database
from hrono.db.migrations import packaged
from hrono.server.app import create_app


def test_startup_creates_db_and_applies_migrations(tmp_path: Path) -> None:
    db = tmp_path / "hrono.db"
    with TestClient(create_app(db_path=db)):
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
    with TestClient(create_app(db_path=db)):
        pass
    with TestClient(create_app(db_path=db)):
        pass
    conn = connect(db, extensions=False)
    count = conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    assert count == len(packaged())
    conn.close()


def test_health_ok_after_startup_wiring(tmp_path: Path) -> None:
    with TestClient(create_app(db_path=tmp_path / "hrono.db")) as client:
        assert client.get("/health").status_code == 200


def test_injected_connection_is_used_and_left_open(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    app = create_app(connection=conn)
    with TestClient(app):
        assert app.state.db is conn
    assert conn.execute("SELECT 1").fetchone()[0] == 1
    conn.close()
