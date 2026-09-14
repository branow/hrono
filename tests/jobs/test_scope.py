import json
import time
from pathlib import Path

import pytest

from hrono.db.database import Database, open_database
from hrono.errors import BadRequest, NotFound
from hrono.jobs import store
from hrono.jobs.ops import Handler
from hrono.jobs.scope import fan_out, resolve
from hrono.jobs.worker import Worker
from hrono.registry import store as registry_store


def database(tmp_path: Path, sources: tuple[str, ...] = ()) -> Database:
    conn = open_database(tmp_path / "hrono.db")
    for name in sources:
        registry_store.insert(
            conn, "sources", name, json.dumps({"name": name}), None, "t"
        )
    return Database.adopt(conn)


def leaves(db: Database, parent_id: str) -> list:
    with db.connect() as conn:
        return [
            row
            for row in store.list_jobs(conn)
            if row["parent_id"] == parent_id
        ]


def status_of(db: Database, job_id: str) -> str | None:
    with db.connect() as conn:
        row = store.get(conn, job_id)
    return row["status"] if row is not None else None


def run_workers(db: Database, ops: dict[str, Handler], count: int = 1) -> list:
    workers = [Worker(db, ops) for _ in range(count)]
    for worker in workers:
        worker.start()
    return workers


def stop(workers: list) -> None:
    for worker in workers:
        worker.stop()
    for worker in workers:
        worker.join(timeout=5)


def wait_all_leaves(db: Database, parent_id: str, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rows = leaves(db, parent_id)
        if rows and all(r["status"] in ("succeeded", "failed") for r in rows):
            return
        time.sleep(0.01)


def test_all_resolves_to_every_source(tmp_path: Path) -> None:
    db = database(tmp_path, ("a", "b", "c"))
    items = resolve(db, {"type": "all"})
    assert {i["name"] for i in items} == {"a", "b", "c"}
    db.close()


def test_omitted_scope_behaves_as_all(tmp_path: Path) -> None:
    db = database(tmp_path, ("a", "b"))
    assert len(resolve(db, None)) == 2
    db.close()


def test_source_resolves_to_one(tmp_path: Path) -> None:
    db = database(tmp_path, ("a", "b"))
    assert resolve(db, {"type": "source", "name": "b"}) == [
        {"type": "source", "name": "b"}
    ]
    db.close()


def test_unknown_source_is_not_found(tmp_path: Path) -> None:
    db = database(tmp_path, ("a",))
    with pytest.raises(NotFound):
        resolve(db, {"type": "source", "name": "ghost"})
    db.close()


@pytest.mark.parametrize("kind", ["section", "node", "level"])
def test_tree_scopes_are_not_yet_supported(tmp_path: Path, kind: str) -> None:
    db = database(tmp_path)
    with pytest.raises(BadRequest):
        resolve(db, {"type": kind})
    db.close()


def test_fan_out_creates_one_leaf_per_source(tmp_path: Path) -> None:
    db = database(tmp_path, ("a", "b"))
    parent = fan_out(db, "noop", {"type": "all"})
    child = leaves(db, parent)
    assert len(child) == 2
    assert {json.loads(r["scope"])["name"] for r in child} == {"a", "b"}
    assert all(json.loads(r["scope"])["type"] == "source" for r in child)
    db.close()


def test_worker_runs_leaves_and_leaves_parent_unrun(tmp_path: Path) -> None:
    db = database(tmp_path, ("a", "b"))
    workers = run_workers(db, {"noop": lambda job, ctx: None})
    try:
        parent = fan_out(db, "noop", {"type": "all"})
        wait_all_leaves(db, parent)
        assert all(r["status"] == "succeeded" for r in leaves(db, parent))
        assert status_of(db, parent) == "pending"
    finally:
        stop(workers)
    db.close()


def test_empty_scope_completes_parent_with_no_leaves(tmp_path: Path) -> None:
    db = database(tmp_path)
    parent = fan_out(db, "noop", {"type": "all"})
    assert leaves(db, parent) == []
    assert status_of(db, parent) == "succeeded"
    db.close()


def test_a_failing_leaf_does_not_block_siblings(tmp_path: Path) -> None:
    def pick(job: object, ctx: object) -> None:
        if job.scope["name"] == "bad":  # type: ignore[attr-defined]
            raise RuntimeError("bad one")

    db = database(tmp_path, ("good", "bad"))
    workers = run_workers(db, {"pick": pick})
    try:
        parent = fan_out(db, "pick", {"type": "all"})
        wait_all_leaves(db, parent)
        by_name = {
            json.loads(r["scope"])["name"]: r["status"]
            for r in leaves(db, parent)
        }
        assert by_name == {"good": "succeeded", "bad": "failed"}
    finally:
        stop(workers)
    db.close()
