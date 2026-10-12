"""A run is journaled as it writes, and reverting it restores it exactly."""

import sqlite3
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db import journal
from hrono.db.database import Database, open_database
from hrono.errors import Conflict
from hrono.jobs import store as job_store
from hrono.server.app import create_app
from tests.tree.test_sync_chain import (  # noqa: F401
    Judge,
    _run,
    _world,
    built,
    tmp_path,
)
from tests.tree.test_update import edit


def _state(conn: sqlite3.Connection) -> dict[str, list[tuple]]:
    """Every journaled row, and the full-text index, as plain tuples."""
    state = {
        table: sorted(
            tuple(row)
            for row in conn.execute(f'SELECT rowid, * FROM "{table}"')  # noqa: S608
        )
        for table in journal.journaled(conn)
    }
    state["passages_fts"] = sorted(
        tuple(row)
        for row in conn.execute(
            "SELECT passage_id, source, path, body FROM passages_fts"
        )
    )
    return state


def _change(origin: Path) -> None:
    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    (origin / "f1.txt").unlink()
    edit(origin, "f9.txt", "a brand new module about caching\n")


def _sync(db: Database, root: Path, run: str) -> None:
    with journal.recording(run):
        _run(db, root, Judge())


def test_reverting_a_sync_restores_every_row(
    built: tuple[Database, Path],  # noqa: F811
    tmp_path: Path,  # noqa: F811
) -> None:
    db, origin = built
    with db.connect() as conn:
        before = _state(conn)
    _change(origin)

    _sync(db, tmp_path, "run-1")
    with db.connect() as conn:
        synced = _state(conn)
    with db.write() as conn:
        undone = journal.revert(conn, "run-1", "admin")
    with db.connect() as conn:
        after = _state(conn)

    assert synced != before
    assert undone > 0
    changed = [t for t in before if before[t] != after[t]]
    assert changed == []


def test_a_reverted_sync_runs_again_the_same_way(
    built: tuple[Database, Path],  # noqa: F811
    tmp_path: Path,  # noqa: F811
) -> None:
    db, origin = built
    _change(origin)

    _sync(db, tmp_path, "run-1")
    with db.connect() as conn:
        first = conn.execute(
            "SELECT tbl, op, COUNT(*) FROM changes WHERE run = 'run-1' "
            "GROUP BY tbl, op ORDER BY tbl, op"
        ).fetchall()
    with db.write() as conn:
        journal.revert(conn, "run-1", None)
    _sync(db, tmp_path, "run-2")
    with db.connect() as conn:
        second = conn.execute(
            "SELECT tbl, op, COUNT(*) FROM changes WHERE run = 'run-2' "
            "GROUP BY tbl, op ORDER BY tbl, op"
        ).fetchall()

    assert [tuple(r) for r in first] == [tuple(r) for r in second]


def test_only_the_newest_run_reverts_and_only_once(
    built: tuple[Database, Path],  # noqa: F811
    tmp_path: Path,  # noqa: F811
) -> None:
    db, origin = built
    _change(origin)
    _sync(db, tmp_path, "run-1")
    edit(origin, "f2.txt", "module 2 changed as well\n")
    _sync(db, tmp_path, "run-2")

    with db.write() as conn, pytest.raises(Conflict, match="revert run-2"):
        journal.revert(conn, "run-1", None)
    with db.write() as conn:
        journal.revert(conn, "run-2", None)
        journal.revert(conn, "run-1", None)
    with db.connect() as conn:
        assert journal.blocker(conn, "run-1") == "already reverted"
        assert [r.reverted for r in journal.runs(conn)] == [True, True]


def test_a_write_outside_a_run_is_not_journaled(
    built: tuple[Database, Path],  # noqa: F811
) -> None:
    db, _ = built
    with db.write() as conn:
        conn.execute("DELETE FROM changes")
        conn.execute("UPDATE nodes SET label = label")

    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM changes").fetchone()[0] == 0


def test_every_table_but_the_listed_ones_is_journaled(
    built: tuple[Database, Path],  # noqa: F811
) -> None:
    db, _ = built
    with db.connect() as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE 'passages_fts%'"
            )
        }
        journaled = set(journal.journaled(conn))

    assert tables - journaled == journal.UNJOURNALED


def test_the_run_page_shows_what_changed_and_reverts_it(
    built: tuple[Database, Path],  # noqa: F811
    tmp_path: Path,  # noqa: F811
) -> None:
    db, origin = built
    _change(origin)
    _sync(db, tmp_path, "run-1")
    with db.write() as conn:
        job_store.insert(conn, "run-1", None, "default", "sync-tree", "{}", "t")
        conn.execute("UPDATE jobs SET status = 'succeeded' WHERE id = 'run-1'")
    db.close()
    key = Fernet.generate_key()
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, key)
    _, admin = create_user(conn, "ada", "admin")
    conn.commit()
    app = create_app(connection=conn, master_key=key, key_id=1)
    with TestClient(app) as client:
        app.state.worker.stop()
        client.post("/ui/login", data={"token": admin})

        page = client.get("/ui/jobs/run-1?tree=default").text
        client.post("/ui/jobs/run-1/revert?tree=default")
        after = client.get("/ui/jobs/run-1?tree=default").text

    assert "What it changed" in page
    assert "topics touched" in page and ">Revert</button>" in page
    assert "Reverted " in after and "topics touched" not in after
