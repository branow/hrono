import json
import time
from collections.abc import Iterator

import pytest

from hrono.cluster import op as cluster_op
from hrono.cluster.blend import path_body, register_path_bodies
from hrono.cluster.build import ClusterResult
from hrono.db.database import Database
from hrono.embed import store as vstore
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.jobs import store as jobs_store
from hrono.jobs.model import Job, serialize_scope
from hrono.jobs.ops import OPS, JobContext
from hrono.jobs.worker import Worker

MODEL = "emb"
DIMS = 4


def register_model(conn: object) -> None:
    body = {
        "name": MODEL,
        "kind": "embedding",
        "connection": None,
        "model": "fake/model",
        "params": {"dims": DIMS},
    }
    from hrono.registry import store as registry_store

    registry_store.insert(conn, "models", MODEL, json.dumps(body), None, "t")  # type: ignore[arg-type]


def add_embedded_section(conn: object, path: str, body: bytes, i: int) -> int:
    istore.upsert_content(conn, content_hash(body), body)  # type: ignore[arg-type]
    register_path_bodies(conn, [path])  # type: ignore[arg-type]
    vstore.upsert_vector(  # type: ignore[arg-type]
        conn, content_hash(body), MODEL, [float(i), 1.0, 0.0, 0.0]
    )
    vstore.upsert_vector(  # type: ignore[arg-type]
        conn, content_hash(path_body(path)), MODEL, [0.0, float(i), 1.0, 0.0]
    )
    return istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "example.com/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=i,
    )


def fake_build(capture: dict[str, object]):
    def build(vectors: object, *, init: object = None) -> ClusterResult:
        capture["init"] = init
        n = len(vectors)  # type: ignore[arg-type]
        labels = tuple(0 if i < (n + 1) // 2 else 1 for i in range(n))
        return ClusterResult(
            labels=labels,
            attached=tuple(False for _ in range(n)),
            assignment_similarity=tuple(None for _ in range(n)),
            coords=tuple((float(i),) * 3 for i in range(n)),
        )

    return build


def cluster_job(job_id: str = "c1", tree: str | None = "default") -> Job:
    return Job(
        id=job_id,
        parent_id=None,
        tree=tree,
        op="cluster",
        scope={"type": "model", "name": MODEL},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_model(conn)
        for i in range(6):
            add_embedded_section(
                conn, f"src/f{i}.py", f"body {i}\n".encode(), i
            )
    yield database
    database.close()


def test_cluster_is_registered() -> None:
    assert "cluster" in OPS


def test_builds_and_persists_a_bottom_level(db: Database) -> None:
    cluster_op.cluster(cluster_job(), JobContext(db), build=fake_build({}))
    with db.connect() as conn:
        nodes = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE tree='default' AND level=0"
        ).fetchone()[0]
        members = conn.execute("SELECT COUNT(*) FROM node_members").fetchone()[
            0
        ]
        coords = conn.execute(
            "SELECT COUNT(*) FROM section_coords WHERE tree='default'"
        ).fetchone()[0]
    assert nodes == 2
    assert members == 6  # every embedded section is a member of exactly one
    assert coords == 6


def test_every_section_in_exactly_one_node(db: Database) -> None:
    cluster_op.cluster(cluster_job(), JobContext(db), build=fake_build({}))
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT section_id, COUNT(*) c FROM node_members "
            "GROUP BY section_id"
        ).fetchall()
    assert rows
    assert all(row["c"] == 1 for row in rows)


def test_warm_init_uses_stored_coords_on_rebuild(db: Database) -> None:
    first: dict[str, object] = {}
    cluster_op.cluster(cluster_job(), JobContext(db), build=fake_build(first))
    assert first["init"] is None  # first build inits fresh

    second: dict[str, object] = {}
    cluster_op.cluster(
        cluster_job("c2"), JobContext(db), build=fake_build(second)
    )
    assert second["init"] is not None  # rebuild warm-inits from stored coords
    assert len(second["init"]) == 6  # type: ignore[arg-type]


def test_empty_corpus_is_a_noop(tmp_path: object) -> None:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_model(conn)
    try:
        cluster_op.cluster(
            cluster_job(), JobContext(database), build=fake_build({})
        )
        with database.connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 0
    finally:
        database.close()


def test_runs_as_a_job_and_persists(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cluster_op, "_load_builder", lambda: fake_build({}))
    worker = Worker(db)
    worker.start()
    try:
        with db.connect() as conn:
            jobs_store.insert(
                conn,
                "cj",
                None,
                "default",
                "cluster",
                serialize_scope({"type": "model", "name": MODEL}),
                "t",
            )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with db.connect() as conn:
                row = conn.execute(
                    "SELECT status FROM jobs WHERE id='cj'"
                ).fetchone()
            if row["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.02)
    finally:
        worker.stop()
        worker.join(timeout=5)  # let the claim query finish before we read
    assert row["status"] == "succeeded"
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 2


def test_failing_run_fails_its_leaf_cleanly(tmp_path: object) -> None:
    # no embedding model registered -> model resolution fails, leaf fails.
    database = Database.at(tmp_path / "hrono.db")
    worker = Worker(database)
    worker.start()
    try:
        with database.connect() as conn:
            jobs_store.insert(
                conn,
                "bad",
                None,
                "default",
                "cluster",
                serialize_scope({"type": "all"}),
                "t",
            )
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with database.connect() as conn:
                row = database_status(conn, "bad")
            if row is not None:
                break
            time.sleep(0.02)
    finally:
        worker.stop()
        worker.join(timeout=5)  # let the claim query finish before close
    assert row == "failed"
    database.close()


def database_status(conn: object, job_id: str) -> str | None:
    row = conn.execute(  # type: ignore[attr-defined]
        "SELECT status FROM jobs WHERE id=?", (job_id,)
    ).fetchone()
    status = row["status"]
    return status if status in ("succeeded", "failed") else None
