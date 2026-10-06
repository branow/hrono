import sqlite3
from pathlib import Path

import pytest

from hrono.db.connection import connect
from hrono.db.migrations import Migrator, packaged


def migrated(tmp_path: Path) -> sqlite3.Connection:
    conn = connect(tmp_path / "hrono.db", extensions=False)
    Migrator(packaged()).apply(conn)
    return conn


def test_jobs_table_shape(tmp_path: Path) -> None:
    conn = migrated(tmp_path)
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(jobs)")}
    assert columns == {
        "id",
        "parent_id",
        "tree",
        "op",
        "scope",
        "status",
        "error",
        "error_code",
        "error_details",
        "created_at",
        "updated_at",
        "heartbeat",
        "result",
        "started_by",
        "attempts",
    }
    conn.close()


def test_jobs_has_status_and_parent_indexes(tmp_path: Path) -> None:
    conn = migrated(tmp_path)
    indexes = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'index' AND tbl_name = 'jobs'"
        )
    }
    assert {"jobs_status", "jobs_parent_id"} <= indexes
    conn.close()


def test_status_check_rejects_unknown_status(tmp_path: Path) -> None:
    conn = migrated(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO jobs (id, op, scope, status, created_at, updated_at) "
            "VALUES ('job_1', 'sync', '{}', 'partial', 't', 't')"
        )
    conn.close()


def test_a_valid_row_round_trips(tmp_path: Path) -> None:
    conn = migrated(tmp_path)
    with conn:
        conn.execute(
            "INSERT INTO jobs (id, op, scope, status, created_at, updated_at) "
            "VALUES ('job_1', 'sync', "
            '\'{"type":"source","name":"repo"}\', '
            "'pending', 't', 't')"
        )
    row = conn.execute("SELECT * FROM jobs WHERE id = 'job_1'").fetchone()
    assert row["op"] == "sync"
    assert row["status"] == "pending"
    conn.close()
