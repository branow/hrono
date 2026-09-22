import json
import time
from collections.abc import Iterator

import numpy as np
import pytest

from hrono.cluster import op as cluster_op
from hrono.cluster.blend import path_body, register_path_bodies
from hrono.cluster.build import ClusterResult, build_clusters
from hrono.cluster.recipe import recipe_for
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


def planted_sources(
    per_source: int, groups: int = 2, dim: int = 16
) -> dict[str, list[list[float]]]:
    """Two sources, each carrying points from the SAME well-separated groups.

    Dropping one source then halves the corpus without erasing a group, so the
    smaller rebuild still has something to cluster.
    """
    rng = np.random.default_rng(0)
    centres = []
    for _ in range(groups):
        centre = rng.normal(size=dim)
        centres.append(centre / np.linalg.norm(centre))
    by_source: dict[str, list[list[float]]] = {}
    for source in ("repo-a", "repo-b"):
        vectors = []
        for i in range(per_source):
            point = centres[i % groups] + 0.05 * rng.normal(size=dim)
            vectors.append((point / np.linalg.norm(point)).tolist())
        by_source[source] = vectors
    return by_source


def add_planted_section(
    conn: object, source: str, i: int, vector: list[float]
) -> int:
    path = f"{source}/f{i}.py"
    body = f"{source} body {i}\n".encode()
    istore.upsert_content(conn, content_hash(body), body)  # type: ignore[arg-type]
    register_path_bodies(conn, [path])  # type: ignore[arg-type]
    vstore.upsert_vector(conn, content_hash(body), MODEL, vector)  # type: ignore[arg-type]
    vstore.upsert_vector(  # type: ignore[arg-type]
        conn, content_hash(path_body(path)), MODEL, vector
    )
    return istore.insert_section(
        conn,  # type: ignore[arg-type]
        source=source,
        address=Address("git", f"example.com/{source}", path, "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=i,
    )


def coord_widths(database: Database) -> set[int]:
    with database.connect() as conn:
        return {
            int(row["dims"])
            for row in conn.execute(
                "SELECT dims FROM section_coords WHERE tree='default'"
            ).fetchall()
        }


@pytest.fixture
def shrinkable(tmp_path: object) -> Iterator[Database]:
    """40 embedded sections split over two sources, ready for the REAL build."""
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_model(conn)
        for source, vectors in planted_sources(20).items():
            for i, vector in enumerate(vectors):
                add_planted_section(conn, source, i, vector)
    yield database
    database.close()


def test_rebuild_across_a_rung_keeps_clustering(shrinkable: Database) -> None:
    # #094: stored coords carry the width of the build that wrote them, and
    # `maintain`/`settle` warm-init every rebuild from them. A corpus that
    # shrinks across the ladder's boundary therefore offers a 25-wide init to
    # a build the recipe reduces to 10 — which used to fail, and to keep
    # failing forever since the stale coords were never rewritten.
    context = JobContext(shrinkable)
    cluster_op.cluster(cluster_job(), context, build=build_clusters)
    assert coord_widths(shrinkable) == {recipe_for(40).n_components}

    with shrinkable.write() as conn:
        istore.clear_source(conn, "repo-b")  # 40 sections -> 20, coords stay

    cluster_op.cluster(cluster_job("c2"), context, build=build_clusters)
    assert coord_widths(shrinkable) == {recipe_for(20).n_components}
    with shrinkable.connect() as conn:
        nodes = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE tree='default' AND level=0"
        ).fetchone()[0]
        members = conn.execute("SELECT COUNT(*) FROM node_members").fetchone()[
            0
        ]
    assert nodes >= 1
    assert members == 20  # the surviving sections are all placed

    # and the tree self-heals: the rewritten coords warm the next build.
    cluster_op.cluster(cluster_job("c3"), context, build=build_clusters)
    assert coord_widths(shrinkable) == {recipe_for(20).n_components}


def database_status(conn: object, job_id: str) -> str | None:
    row = conn.execute(  # type: ignore[attr-defined]
        "SELECT status FROM jobs WHERE id=?", (job_id,)
    ).fetchone()
    status = row["status"]
    return status if status in ("succeeded", "failed") else None


def test_a_collected_build_says_it_collected(tmp_path: object) -> None:
    # #133: a one-topic tree is a legitimate answer for a small corpus and a
    # surprising one for a large one. From outside they look identical unless
    # the run says which happened.
    database = Database.at(tmp_path / "small.db")
    try:
        with database.connect() as conn, conn:
            register_model(conn)
            for i in range(3):  # below MIN_POINTS: the ladder declines
                add_embedded_section(
                    conn, f"src/t{i}.py", f"tiny {i}\n".encode(), i
                )

        outcome = cluster_op.cluster(cluster_job(), JobContext(database))

        assert outcome["collected"] is True
        assert outcome["topics"] == 1
        assert outcome["sections"] == 3
    finally:
        database.close()


def test_a_real_clustered_build_says_it_did_not_collect(db: Database) -> None:
    outcome = cluster_op.cluster(
        cluster_job(), JobContext(db), build=fake_build({})
    )

    assert outcome["collected"] is False
    assert outcome["sections"] > 0
