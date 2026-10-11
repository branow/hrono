import sqlite3
from pathlib import Path

import pytest

from hrono.db.connection import connect


def test_creates_missing_parent_directory(tmp_path: Path) -> None:
    db = tmp_path / "nested" / "here" / "hrono.db"
    connect(db, extensions=False)
    assert db.exists()


def test_uses_wal_journal(tmp_path: Path) -> None:
    conn = connect(tmp_path / "hrono.db", extensions=False)
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"


def test_enforces_foreign_keys(tmp_path: Path) -> None:
    conn = connect(tmp_path / "hrono.db", extensions=False)
    conn.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
    conn.execute("CREATE TABLE child (parent_id INTEGER REFERENCES parent(id))")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO child (parent_id) VALUES (999)")
        conn.commit()


def test_a_read_opens_no_transaction(tmp_path: Path) -> None:
    conn = connect(tmp_path / "hrono.db", extensions=False)
    conn.execute("CREATE TABLE t (n INTEGER)")
    conn.execute("SELECT count(*) FROM t").fetchone()
    assert conn.in_transaction is False


def test_a_write_opens_an_immediate_transaction(tmp_path: Path) -> None:
    conn = connect(tmp_path / "hrono.db", extensions=False)
    conn.execute("CREATE TABLE t (n INTEGER)")
    conn.execute("INSERT INTO t VALUES (1)")
    assert conn.in_transaction is True
    assert conn.isolation_level == "IMMEDIATE"

    blocked = connect(tmp_path / "hrono.db", extensions=False)
    blocked.execute("PRAGMA busy_timeout=50")
    with pytest.raises(sqlite3.OperationalError):
        blocked.execute("BEGIN IMMEDIATE")
    conn.commit()


def test_loads_sqlite_vec(tmp_path: Path) -> None:
    conn = connect(tmp_path / "hrono.db", extensions=True)
    version = conn.execute("SELECT vec_version()").fetchone()[0]
    assert version
