"""T35: the incubator pending pool — park, drain, force-assign, aging."""

from collections.abc import Iterator

import pytest

from hrono.cluster import incubator
from hrono.cluster import store as cluster_store
from hrono.cluster.blend import path_body, register_path_bodies
from hrono.cluster.recipe import MIN_POINTS
from hrono.db.database import Database
from hrono.embed.store import upsert_vector
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from tests.cluster.harness import planted_groups

MODEL = "emb"
DIMS = 4
PATH = "src/x.py"
TREE = "default"


def unit(i: int) -> list[float]:
    v = [0.0] * DIMS
    v[i] = 1.0
    return v


def add_section(conn: object, body: bytes, content_vec: list[float]) -> str:
    digest = content_hash(body)
    upsert_content(conn, digest, body)  # type: ignore[arg-type]
    upsert_vector(conn, digest, MODEL, content_vec)  # type: ignore[arg-type]
    insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "ex/repo", PATH, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )
    return digest


def content_core_labeler(vectors):
    # content e1 -> a density core (label 0); content e0 -> noise (-1)
    return [0 if v[1] > 0.5 else -1 for v in vectors]


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_path_bodies(conn, [PATH])
        upsert_vector(conn, content_hash(path_body(PATH)), MODEL, unit(2))
        # one EXISTING cluster whose content is e0 (force-assign target)
        existing = add_section(conn, b"existing chunk\n", unit(0))
        cluster_store.add_leaf_node(
            conn,
            TREE,
            [(_sid(conn, existing), False, None)],
        )
    yield database
    database.close()


def _sid(conn: object, digest: str) -> int:
    return int(
        conn.execute(  # type: ignore[attr-defined]
            "SELECT id FROM sections WHERE content_hash = ?", (digest,)
        ).fetchone()["id"]
    )


def _members(db: Database, node_id: int) -> int:
    with db.connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM node_members WHERE node_id = ?",
                (node_id,),
            ).fetchone()[0]
        )


def test_park_pending_and_unpark(db: Database) -> None:
    with db.connect() as conn, conn:
        digest = add_section(conn, b"parked\n", unit(1))
        incubator.park(conn, TREE, digest, PATH, batch=1)
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 1
        assert incubator.pending(conn, TREE)[0][0] == digest
    with db.connect() as conn, conn:
        incubator.unpark(conn, TREE, digest)
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 0


def test_below_min_does_not_drain(db: Database) -> None:
    with db.connect() as conn, conn:
        for i in range(3):
            d = add_section(conn, f"c{i}\n".encode(), unit(1))
            incubator.park(conn, TREE, d, PATH, batch=1)
    with db.connect() as conn, conn:
        assert incubator.drain(conn, TREE, MODEL) is False
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 3  # still pending


def test_drain_emits_cores_and_force_assigns_residual(db: Database) -> None:
    existing_node = 1  # the fixture's only node
    with db.connect() as conn, conn:
        for i in range(MIN_POINTS - 1):  # e1 chunks -> one density core
            d = add_section(conn, f"core{i}\n".encode(), unit(1))
            incubator.park(conn, TREE, d, PATH, batch=1)
        residual = add_section(conn, b"residual\n", unit(0))  # near existing
        incubator.park(conn, TREE, residual, PATH, batch=1)
    with db.connect() as conn, conn:
        assert incubator.drain(
            conn, TREE, MODEL, core_labeler=content_core_labeler
        )
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 0  # pool emptied
        level0 = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE tree = ? AND level = 0", (TREE,)
        ).fetchone()[0]
        assert level0 == 2  # the existing node + one new core node
        # the residual was force-assigned to the existing cluster, flagged
        forced = conn.execute(
            "SELECT COUNT(*) FROM node_members WHERE forced = 1"
        ).fetchone()[0]
        assert forced == 1
    assert _members(db, existing_node) == 2  # original + forced residual


def test_aging_force_assigns_an_old_pending_chunk(db: Database) -> None:
    with db.connect() as conn, conn:
        old = add_section(conn, b"old pending\n", unit(0))
        incubator.park(conn, TREE, old, PATH, batch=1)
    with db.connect() as conn, conn:
        # batch 10 vs parked at 1, max_age 5 -> aged out, pool below min
        forced = incubator.age(conn, TREE, MODEL, current_batch=10, max_age=5)
    assert forced == 1
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 0  # no longer pending
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM node_members WHERE forced = 1"
            ).fetchone()[0]
            == 1
        )


def test_young_pending_chunk_is_not_aged_out(db: Database) -> None:
    with db.connect() as conn, conn:
        d = add_section(conn, b"young\n", unit(0))
        incubator.park(conn, TREE, d, PATH, batch=8)
    with db.connect() as conn, conn:
        assert (
            incubator.age(conn, TREE, MODEL, current_batch=10, max_age=5) == 0
        )
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 1  # still waiting


def test_a_pool_the_clusterer_cannot_reduce_does_not_raise(
    db: Database,
) -> None:
    # #094: the drain gate is the clusterer's own minimum, so a 5-chunk pool
    # takes the real mini-pipeline nowhere near a driver exception.
    with db.connect() as conn, conn:
        for i in range(5):
            d = add_section(conn, f"small{i}\n".encode(), unit(1))
            incubator.park(conn, TREE, d, PATH, batch=1)
    with db.connect() as conn, conn:
        assert incubator.drain(conn, TREE, MODEL) is False
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 5  # still pending, intact


PLANTED_DIMS = 40


@pytest.fixture
def planted(tmp_path: object) -> Iterator[Database]:
    """A pool of two well-separated planted groups plus one existing node."""
    vectors, _ = planted_groups(
        groups=2, per_group=7, dim=PLANTED_DIMS, spread=0.1, noise=0, seed=1
    )
    database = Database.at(tmp_path / "planted.db")
    with database.connect() as conn, conn:
        register_path_bodies(conn, [PATH])
        upsert_vector(
            conn,
            content_hash(path_body(PATH)),
            MODEL,
            [1.0] + [0.0] * (PLANTED_DIMS - 1),
        )
        existing = add_section(
            conn, b"existing planted\n", [0.0] * (PLANTED_DIMS - 1) + [1.0]
        )
        cluster_store.add_leaf_node(
            conn, TREE, [(_sid(conn, existing), False, None)]
        )
        for i, vector in enumerate(vectors):
            digest = add_section(
                conn, f"planted {i}\n".encode(), [float(v) for v in vector]
            )
            incubator.park(conn, TREE, digest, PATH, batch=1)
    yield database
    database.close()


def _log(db: Database) -> list[tuple[str, str]]:
    with db.connect() as conn:
        return [
            (row["verdict"], row["action"])
            for row in conn.execute(
                "SELECT verdict, action FROM update_log ORDER BY id"
            ).fetchall()
        ]


def _level0(db: Database) -> int:
    with db.connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE tree = ? AND level = 0",
                (TREE,),
            ).fetchone()[0]
        )


def test_the_real_mini_pipeline_drains_a_planted_pool(
    planted: Database,
) -> None:
    # no `core_labeler` seam: the REAL UMAP -> HDBSCAN leaf recipe reduces the
    # pool, so the drain's contract is proven against the backend it ships with.
    before = _level0(planted)
    with planted.connect() as conn, conn:
        assert incubator.drain(conn, TREE, MODEL) is True
    with planted.connect() as conn:
        assert incubator.count(conn, TREE) == 0
    assert _level0(planted) == before + 2  # both planted groups became nodes
    assert _log(planted).count(("drain", "core")) == 2


def test_drain_and_age_are_written_to_the_update_log(db: Database) -> None:
    with db.connect() as conn, conn:
        old = add_section(conn, b"old pending\n", unit(0))
        incubator.park(conn, TREE, old, PATH, batch=1)
    with db.connect() as conn, conn:
        incubator.age(conn, TREE, MODEL, current_batch=10)
    assert _log(db) == [("age", "forced")]


def test_age_empties_a_pool_the_clusterer_can_never_reduce(
    db: Database,
) -> None:
    # #095: the age gate is the DRAINABLE size, so a pool that is big enough to
    # look full but has no usable vectors still ages out instead of stranding.
    with db.connect() as conn, conn:
        for i in range(MIN_POINTS + 3):
            digest = add_section(conn, f"blind{i}\n".encode(), unit(0))
            conn.execute(
                "DELETE FROM embeddings WHERE content_hash = ?", (digest,)
            )
            incubator.park(conn, TREE, digest, PATH, batch=1)
        placeable = add_section(conn, b"placeable\n", unit(0))
        incubator.park(conn, TREE, placeable, PATH, batch=1)
    with db.connect() as conn, conn:
        assert incubator.age(conn, TREE, MODEL, current_batch=10) == 1
    with db.connect() as conn:
        assert incubator.pending(conn, TREE) and all(
            entry[0] != placeable for entry in incubator.pending(conn, TREE)
        )


def test_sweep_retires_pool_rows_a_rebuild_has_already_homed(
    db: Database,
) -> None:
    with db.connect() as conn, conn:
        digest = add_section(conn, b"rehomed\n", unit(1))
        incubator.park(conn, TREE, digest, PATH, batch=1)
        cluster_store.add_member(
            conn, 1, _sid(conn, digest), forced=False, similarity=0.9
        )
    with db.connect() as conn, conn:
        assert incubator.sweep(conn, TREE) == 1
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 0


def test_sweep_leaves_a_genuinely_homeless_chunk_alone(db: Database) -> None:
    with db.connect() as conn, conn:
        digest = add_section(conn, b"homeless\n", unit(1))
        incubator.park(conn, TREE, digest, PATH, batch=1)
    with db.connect() as conn, conn:
        assert incubator.sweep(conn, TREE) == 0
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 1
