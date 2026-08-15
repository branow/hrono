import sqlite3
from pathlib import Path

import pytest

from hrono.db.connection import connect
from hrono.db.migrations import DuplicateVersion, Migration, Migrator, discover


def make_conn(tmp_path: Path) -> sqlite3.Connection:
    return connect(tmp_path / "hrono.db", extensions=False)


def write(directory: Path, name: str, sql: str) -> None:
    (directory / name).write_text(sql)


def test_discover_orders_by_version(tmp_path: Path) -> None:
    write(tmp_path, "0002_second.sql", "SELECT 1")
    write(tmp_path, "0001_first.sql", "SELECT 1")
    write(tmp_path, "0010_tenth.sql", "SELECT 1")
    versions = [m.version for m in discover(tmp_path)]
    assert versions == [1, 2, 10]


def test_discover_ignores_non_migration_files(tmp_path: Path) -> None:
    write(tmp_path, "0001_real.sql", "SELECT 1")
    write(tmp_path, "README.sql", "SELECT 1")
    write(tmp_path, "notes.txt", "ignore me")
    names = [m.name for m in discover(tmp_path)]
    assert names == ["real"]


def test_discover_rejects_duplicate_versions(tmp_path: Path) -> None:
    write(tmp_path, "0001_one.sql", "SELECT 1")
    write(tmp_path, "0001_other.sql", "SELECT 1")
    with pytest.raises(DuplicateVersion):
        discover(tmp_path)


def test_apply_runs_pending_and_records_versions(tmp_path: Path) -> None:
    conn = make_conn(tmp_path)
    migrator = Migrator(
        (Migration(1, "create_widgets", "CREATE TABLE widgets (id INTEGER)"),)
    )
    applied = migrator.apply(conn)
    assert applied == (1,)
    recorded = conn.execute(
        "SELECT version, name FROM schema_migrations"
    ).fetchall()
    assert [tuple(r) for r in recorded] == [(1, "create_widgets")]
    conn.execute("INSERT INTO widgets (id) VALUES (1)")


def test_apply_is_idempotent(tmp_path: Path) -> None:
    conn = make_conn(tmp_path)
    migrator = Migrator(
        (Migration(1, "create_widgets", "CREATE TABLE widgets (id INTEGER)"),)
    )
    migrator.apply(conn)
    assert migrator.apply(conn) == ()
    assert migrator.pending(conn) == ()


def test_apply_runs_only_new_migrations_across_calls(tmp_path: Path) -> None:
    conn = make_conn(tmp_path)
    first = Migration(1, "one", "CREATE TABLE a (id INTEGER)")
    second = Migration(2, "two", "CREATE TABLE b (id INTEGER)")
    Migrator((first,)).apply(conn)
    assert Migrator((first, second)).apply(conn) == (2,)


def test_apply_runs_in_version_order(tmp_path: Path) -> None:
    conn = make_conn(tmp_path)
    migrations = (
        Migration(2, "add_column", "ALTER TABLE t ADD COLUMN note TEXT"),
        Migration(1, "create_table", "CREATE TABLE t (id INTEGER)"),
    )
    Migrator(migrations).apply(conn)
    order = [
        r[0]
        for r in conn.execute(
            "SELECT version FROM schema_migrations ORDER BY applied_at"
        )
    ]
    assert order == [1, 2]


def test_failed_migration_rolls_back_fully(tmp_path: Path) -> None:
    conn = make_conn(tmp_path)
    broken = Migration(
        1, "broken", "CREATE TABLE good (id INTEGER); CREATE TABLE bad (;"
    )
    migrator = Migrator((broken,))
    with pytest.raises(sqlite3.OperationalError):
        migrator.apply(conn)
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    names = {r[0] for r in tables}
    assert "good" not in names
    count = conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0]
    assert count == 0
