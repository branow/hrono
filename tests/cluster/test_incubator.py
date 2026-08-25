"""T35: the incubator pending pool — park, drain, force-assign, aging."""

from collections.abc import Iterator

import pytest

from hrono.cluster import incubator
from hrono.cluster import store as cluster_store
from hrono.cluster.blend import path_body, register_path_bodies
from hrono.db.database import Database, open_database
from hrono.embed.store import upsert_vector
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content

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
    database = Database(open_database(tmp_path / "hrono.db"))  # type: ignore[operator]
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
        for i in range(5):  # 5 e1 chunks -> one density core
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
