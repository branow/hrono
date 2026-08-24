import hashlib
import json
from collections.abc import Iterator

import pytest

from hrono.cluster.levels import cluster_briefs
from hrono.db.database import Database, open_database
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.registry import store as registry_store
from hrono.summarize import briefs

DIMS = 16


def register_embedding_model(conn: object) -> None:
    body = {
        "name": "emb",
        "kind": "embedding",
        "connection": None,
        "model": "fake/model",
        "params": {"dims": DIMS, "batch_size": 8},
    }
    registry_store.insert(conn, "models", "emb", json.dumps(body), None, "t")  # type: ignore[arg-type]


def build_level0(conn: object, per_group: int = 10) -> dict[int, str]:
    """Create 2 groups of level-0 nodes, each with a group-separable brief."""
    node_group: dict[int, str] = {}
    for group, name in enumerate(("alpha", "beta")):
        for i in range(per_group):
            cursor = conn.execute(  # type: ignore[attr-defined]
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES ('default', 0, ?, 't')",
                (group,),
            )
            node_id = int(cursor.lastrowid)
            briefs.upsert(
                conn,  # type: ignore[arg-type]
                node_id,
                f"{name} topic number {i}",
                model_name="emb",
                prompt_name="brief",
                prompt_hash="h",
                input_tokens=1,
                output_tokens=1,
            )
            node_group[node_id] = name
    return node_group


def fake_encoder_for(calls: list[int]):
    def build(model_id: str):
        def encode(texts: list[str]) -> list[list[float]]:
            calls.append(len(texts))
            out = []
            for text in texts:
                base = [0.0] * DIMS
                base[0 if "alpha" in text else 1] = 1.0
                digest = int(hashlib.sha256(text.encode()).hexdigest(), 16)
                out.append(
                    [
                        b + ((digest >> (i * 2)) & 3) / 300.0
                        for i, b in enumerate(base)
                    ]
                )
            return out

        return encode

    return build


def job(level: int = 0) -> Job:
    return Job(
        id="cb1",
        parent_id=None,
        tree="default",
        op="cluster-briefs",
        scope={"level": level},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def seeded(tmp_path: object) -> Iterator[tuple[Database, dict[int, str]]]:
    database = Database(open_database(tmp_path / "hrono.db"))  # type: ignore[operator]
    with database.connect() as conn, conn:
        register_embedding_model(conn)
        node_group = build_level0(conn)
    yield database, node_group
    database.close()


def _partition(
    db: Database, node_group: dict[int, str]
) -> list[frozenset[str]]:
    with db.connect() as conn:
        parents = [
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM nodes WHERE level = 1 ORDER BY id"
            ).fetchall()
        ]
        return [
            frozenset(
                node_group[int(r["child_id"])]
                for r in conn.execute(
                    "SELECT child_id FROM node_children WHERE parent_id = ?",
                    (parent,),
                ).fetchall()
            )
            for parent in parents
        ]


def test_cluster_briefs_is_registered() -> None:
    assert "cluster-briefs" in OPS


def test_briefs_cluster_into_a_coherent_next_level(
    seeded: tuple[Database, dict[int, str]],
) -> None:
    db, node_group = seeded
    cluster_briefs(job(), JobContext(db), encoder_for=fake_encoder_for([]))
    with db.connect() as conn:
        level1 = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE level = 1"
        ).fetchone()[0]
        children = conn.execute(
            "SELECT COUNT(*) FROM node_children"
        ).fetchone()[0]
        distinct = conn.execute(
            "SELECT COUNT(DISTINCT child_id) FROM node_children"
        ).fetchone()[0]
    assert level1 == 2  # the two planted groups recovered
    assert children == 20  # every level-0 node is a member
    assert distinct == 20  # each in exactly one parent (full coverage)
    # each recovered cluster is a single planted group
    assert sorted(_partition(db, node_group)) == [
        frozenset({"alpha"}),
        frozenset({"beta"}),
    ]


def test_members_are_node_ids_not_sections(
    seeded: tuple[Database, dict[int, str]],
) -> None:
    db, node_group = seeded
    cluster_briefs(job(), JobContext(db), encoder_for=fake_encoder_for([]))
    with db.connect() as conn:
        child_ids = {
            int(r["child_id"])
            for r in conn.execute(
                "SELECT child_id FROM node_children"
            ).fetchall()
        }
    assert child_ids == set(node_group)  # exactly the level-0 node ids


def test_brief_embedding_is_embed_once(
    seeded: tuple[Database, dict[int, str]],
) -> None:
    db, _ = seeded
    calls: list[int] = []
    cluster_briefs(job(), JobContext(db), encoder_for=fake_encoder_for(calls))
    assert sum(calls) == 20  # all briefs embedded on the first pass
    # a re-run finds every brief already embedded -> no new encode work
    before = len(calls)
    cluster_briefs(job(), JobContext(db), encoder_for=fake_encoder_for(calls))
    assert len(calls) == before


def test_clustering_is_deterministic(tmp_path: object) -> None:
    groups = []
    for name in ("a", "b"):
        database = Database(open_database(tmp_path / f"{name}.db"))  # type: ignore[operator]
        with database.connect() as conn, conn:
            register_embedding_model(conn)
            node_group = build_level0(conn)
        cluster_briefs(
            job(), JobContext(database), encoder_for=fake_encoder_for([])
        )
        groups.append(sorted(_partition(database, node_group)))
        database.close()
    assert groups[0] == groups[1]
