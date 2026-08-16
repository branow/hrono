import dataclasses
import sqlite3
from pathlib import Path

import pytest

from hrono.db.connection import connect
from hrono.db.migrations import Migrator, packaged
from hrono.jobs.model import (
    Job,
    JobStatus,
    deserialize_scope,
    serialize_scope,
    to_job,
)


def test_status_set_is_exactly_the_five_leaf_statuses() -> None:
    assert {s.value for s in JobStatus} == {
        "pending",
        "running",
        "succeeded",
        "failed",
        "canceled",
    }
    assert "partial" not in {s.value for s in JobStatus}


def test_job_is_frozen() -> None:
    job = Job(
        id="job_1",
        parent_id=None,
        tree=None,
        op="sync",
        scope={"type": "all"},
        status="pending",
        error=None,
        created_at="t",
        updated_at="t",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        job.status = "running"  # type: ignore[misc]


def test_scope_round_trips() -> None:
    scope = {"type": "source", "name": "webphone"}
    assert deserialize_scope(serialize_scope(scope)) == scope


def test_row_reads_into_a_job(tmp_path: Path) -> None:
    conn = connect(tmp_path / "hrono.db", extensions=False)
    Migrator(packaged()).apply(conn)
    with conn:
        conn.execute(
            "INSERT INTO jobs "
            "(id, parent_id, tree, op, scope, status, created_at, updated_at) "
            "VALUES ('job_1', 'job_0', 'main', 'sync', ?, 'running', 't', 'u')",
            (serialize_scope({"type": "all"}),),
        )
    row: sqlite3.Row = conn.execute(
        "SELECT * FROM jobs WHERE id = 'job_1'"
    ).fetchone()
    job = to_job(row)
    assert job == Job(
        id="job_1",
        parent_id="job_0",
        tree="main",
        op="sync",
        scope={"type": "all"},
        status="running",
        error=None,
        created_at="t",
        updated_at="u",
    )
    conn.close()
