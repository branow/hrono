import threading
from pathlib import Path

import pytest

from hrono.db.database import Database, open_database
from hrono.db.migrations import Migrator, packaged


def test_open_database_applies_packaged_migrations(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    applied = {
        row["version"]
        for row in conn.execute("SELECT version FROM schema_migrations")
    }
    assert applied == {m.version for m in packaged()}
    assert applied
    keys = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='keys'"
    ).fetchone()
    assert keys is not None
    conn.close()


def test_open_database_is_idempotent_across_restarts(tmp_path: Path) -> None:
    db = tmp_path / "hrono.db"
    open_database(db).close()
    conn = open_database(db)
    assert Migrator(packaged()).pending(conn) == ()
    count = conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    assert count == len(packaged())
    conn.close()


def test_open_database_resolves_migrations_independent_of_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    conn = open_database(tmp_path / "hrono.db")
    keys = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='keys'"
    ).fetchone()
    assert keys is not None
    conn.close()


def test_open_database_default_path_is_dot_hrono() -> None:
    from hrono.db.database import DEFAULT_PATH

    assert Path(".hrono/hrono.db") == DEFAULT_PATH


def test_database_serializes_concurrent_cross_thread_access(
    tmp_path: Path,
) -> None:
    database = Database(open_database(tmp_path / "hrono.db"))
    with database.connect() as conn:
        conn.execute("CREATE TABLE probe (n INTEGER)")
        conn.commit()

    errors: list[Exception] = []

    def worker() -> None:
        try:
            for _ in range(50):
                with database.connect() as conn, conn:
                    conn.execute("INSERT INTO probe (n) VALUES (1)")
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    with database.connect() as conn:
        total = conn.execute("SELECT count(*) FROM probe").fetchone()[0]
    assert total == 8 * 50
    database.close()
