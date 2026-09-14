import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from hrono.db.connection import connect
from hrono.db.database import Database, open_database
from hrono.db.migrations import Migrator, packaged
from hrono.errors import Unavailable


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


def test_database_handles_concurrent_cross_thread_writers(
    tmp_path: Path,
) -> None:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn:
        conn.execute("CREATE TABLE probe (n INTEGER)")
        conn.commit()

    errors: list[Exception] = []

    def worker() -> None:
        try:
            for _ in range(50):
                with database.write() as conn:
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


def _probe_table(database: Database) -> None:
    with database.write() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS probe (n INTEGER)")


def test_a_failed_block_leaves_the_next_caller_a_clean_connection(
    tmp_path: Path,
) -> None:
    """F23: an op that raised left the shared connection in a transaction,
    after which every write returned 'database is locked' for ever."""
    database = Database.at(tmp_path / "hrono.db")
    _probe_table(database)

    with pytest.raises(RuntimeError):  # noqa: SIM117
        with database.write() as conn:
            conn.execute("INSERT INTO probe (n) VALUES (1)")
            raise RuntimeError("op blew up mid-transaction")

    with database.write() as conn:
        conn.execute("INSERT INTO probe (n) VALUES (2)")
    with database.connect() as conn:
        rows = [row[0] for row in conn.execute("SELECT n FROM probe")]
        assert conn.in_transaction is False
    assert rows == [2]
    database.close()


def test_a_foreign_commit_is_visible_to_the_next_read(tmp_path: Path) -> None:
    """F23: a committed row stayed invisible to the server for 20 minutes."""
    db = tmp_path / "hrono.db"
    database = Database.at(db)
    _probe_table(database)
    with database.connect() as conn:
        assert conn.execute("SELECT count(*) FROM probe").fetchone()[0] == 0

    foreign = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sqlite3,sys;"
            "c=sqlite3.connect(sys.argv[1]);"
            "c.execute('INSERT INTO probe VALUES (7)');c.commit();c.close()",
            str(db),
        ],
        capture_output=True,
        check=False,
    )
    assert foreign.returncode == 0, foreign.stderr

    with database.connect() as conn:
        assert [row[0] for row in conn.execute("SELECT n FROM probe")] == [7]
    database.close()


def test_a_write_waits_out_another_writer_instead_of_failing(
    tmp_path: Path,
) -> None:
    """F13: an 11-minute job died the instant another process wrote a row."""
    db = tmp_path / "hrono.db"
    database = Database.at(db)
    _probe_table(database)

    holding = threading.Event()
    rival = connect(db, extensions=False)

    def hold() -> None:
        rival.execute("BEGIN IMMEDIATE")
        rival.execute("INSERT INTO probe (n) VALUES (1)")
        holding.set()
        time.sleep(0.3)
        rival.commit()

    keeper = threading.Thread(target=hold)
    keeper.start()
    assert holding.wait(timeout=5)

    with database.write() as conn:
        conn.execute("INSERT INTO probe (n) VALUES (2)")
    keeper.join()
    rival.close()

    with database.connect() as conn:
        assert conn.execute("SELECT count(*) FROM probe").fetchone()[0] == 2
    database.close()


def test_an_unavailable_database_raises_a_mapped_app_error(
    tmp_path: Path,
) -> None:
    db = tmp_path / "hrono.db"
    database = Database.at(db)
    _probe_table(database)

    impatient = open_database(db)
    impatient.execute("PRAGMA busy_timeout=0")
    rival = connect(db, extensions=False)
    rival.execute("BEGIN IMMEDIATE")
    rival.execute("INSERT INTO probe (n) VALUES (1)")

    started = time.monotonic()
    with pytest.raises(Unavailable) as raised:  # noqa: SIM117
        with Database.adopt(impatient).write() as conn:
            conn.execute("INSERT INTO probe (n) VALUES (2)")
    waited = time.monotonic() - started

    assert "busy" in raised.value.message
    assert waited >= 0.3  # it backed off between attempts, it did not give up
    assert impatient.in_transaction is False
    rival.rollback()
    rival.close()
    impatient.close()
    database.close()


def test_a_long_write_does_not_wedge_or_stale_the_other_connections(
    tmp_path: Path,
) -> None:
    """F23 end to end: a writer in flight must not freeze readers' snapshots."""
    db = tmp_path / "hrono.db"
    database = Database.at(db)
    _probe_table(database)

    with database.connect() as conn:
        before = conn.execute("SELECT count(*) FROM probe").fetchone()[0]

    started = threading.Event()
    finished = threading.Event()

    def long_write() -> None:
        with database.write() as conn:
            conn.execute("INSERT INTO probe (n) VALUES (1)")
            started.set()
            finished.wait(timeout=5)

    writer = threading.Thread(target=long_write)
    writer.start()
    assert started.wait(timeout=5)

    foreign = connect(db, extensions=False)
    with database.connect() as conn:
        during = conn.execute("SELECT count(*) FROM probe").fetchone()[0]
    finished.set()
    writer.join()

    foreign.execute("INSERT INTO probe (n) VALUES (2)")
    foreign.commit()
    foreign.close()

    with database.connect() as conn:
        after = conn.execute("SELECT count(*) FROM probe").fetchone()[0]
    assert (before, during, after) == (0, 0, 2)
    database.close()


def test_nested_borrows_share_one_transaction(tmp_path: Path) -> None:
    database = Database.at(tmp_path / "hrono.db")
    _probe_table(database)

    with pytest.raises(RuntimeError):  # noqa: SIM117
        with database.write() as outer:
            outer.execute("INSERT INTO probe (n) VALUES (1)")
            with database.write() as inner:
                assert inner is outer
                inner.execute("INSERT INTO probe (n) VALUES (2)")
            raise RuntimeError("the outer op failed after the inner one")

    with database.connect() as conn:
        assert conn.execute("SELECT count(*) FROM probe").fetchone()[0] == 0
    database.close()
