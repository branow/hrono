import sqlite3
from pathlib import Path

import pytest

from hrono.db import migrations
from hrono.db.connection import connect
from hrono.db.migrations import Migrator, discover

MIGRATIONS = Path(migrations.__file__).parent / "migrations"


def apply_migrations(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "hrono.db", extensions=False)
    Migrator(discover(MIGRATIONS)).apply(conn)
    return conn


def test_keys_migration_creates_table_shape(tmp_path: Path) -> None:
    conn = apply_migrations(tmp_path)
    columns = {
        row["name"]: row for row in conn.execute("PRAGMA table_info(keys)")
    }
    assert set(columns) == {"key_id", "key_hash", "created_at"}
    assert columns["key_id"]["pk"] == 1
    assert columns["key_hash"]["notnull"] == 1
    assert columns["created_at"]["notnull"] == 1


def test_keys_migration_enforces_unique_key_hash(tmp_path: Path) -> None:
    conn = apply_migrations(tmp_path)
    conn.execute(
        "INSERT INTO keys (key_hash, created_at) VALUES (?, ?)",
        ("abc", "2026-08-15T00:00:00+00:00"),
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO keys (key_hash, created_at) VALUES (?, ?)",
            ("abc", "2026-08-15T00:00:01+00:00"),
        )
