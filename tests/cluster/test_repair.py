"""T38: local cluster repairs — split, migrate, dissolve."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import incubator, monitor, repair
from hrono.cluster import store as cluster_store
from hrono.cluster.blend import path_body, register_path_bodies
from hrono.db.database import Database
from hrono.embed.store import upsert_vector
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS
from hrono.registry import store as registry_store
from tests.context import job_context

MODEL = "emb"
DIMS = 4
PATH = "src/x.py"
TREE = "default"


def unit(i: int) -> list[float]:
    v = [0.0] * DIMS
    v[i] = 1.0
    return v


def add_section(conn: object, body: bytes, vec: list[float]) -> int:
    digest = content_hash(body)
    upsert_content(conn, digest, body)  # type: ignore[arg-type]
    upsert_vector(conn, digest, MODEL, vec)  # type: ignore[arg-type]
    return insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "ex/repo", PATH, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )


def node_of(conn: object, sections: list[int]) -> int:
    return cluster_store.add_leaf_node(
        conn, TREE, [(s, False, None) for s in sections]
    )


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_path_bodies(conn, [PATH])
        upsert_vector(conn, content_hash(path_body(PATH)), MODEL, unit(2))
        registry_store.insert(
            conn,
            "models",
            MODEL,
            '{"name":"emb","kind":"embedding","connection":null,'
            '"model":"fake","params":{"dims":4}}',
            None,
            "t",
        )
    yield database
    database.close()


def _job() -> Job:
    return Job(
        id="rep",
        parent_id=None,
        tree=TREE,
        op="repair",
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


def test_registered() -> None:
    assert "repair" in OPS


def test_split_breaks_an_oversized_cluster_into_children(db: Database) -> None:
    # 32 members > MAX_CAP(30): 16 of topic 0, 16 of topic 1, in one node
    with db.connect() as conn, conn:
        sections = [
            add_section(conn, f"a{i}\n".encode(), unit(0)) for i in range(16)
        ]
        sections += [
            add_section(conn, f"b{i}\n".encode(), unit(1)) for i in range(16)
        ]
        big = node_of(conn, sections)

    def labeler(vectors: list[list[float]]) -> list[int]:
        return [0 if v[1] > 0.5 else 1 for v in vectors]  # split by topic

    with db.connect() as conn, conn:
        children = repair.split(conn, TREE, big, MODEL, core_labeler=labeler)
    assert len(children) == 2
    with db.connect() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE id = ?", (big,)
            ).fetchone()[0]
            == 0
        )  # oversized node retired
        for child in children:
            n = cluster_store.member_count(conn, child)
            assert 5 <= n <= 20
            # new nodes carry a #068 signature so a rebuild can match them
            sig = conn.execute(
                "SELECT signature FROM nodes WHERE id = ?", (child,)
            ).fetchone()["signature"]
            assert sig is not None


def test_split_leaves_a_within_cap_cluster_alone(db: Database) -> None:
    with db.connect() as conn, conn:
        small = node_of(
            conn,
            [add_section(conn, f"s{i}\n".encode(), unit(0)) for i in range(6)],
        )
    with db.connect() as conn, conn:
        assert repair.split(conn, TREE, small, MODEL) == ()
    with db.connect() as conn:
        assert cluster_store.member_count(conn, small) == 6


def test_migrate_moves_misfit_chunks_to_their_best_cluster(
    db: Database,
) -> None:
    with db.connect() as conn, conn:
        # A is mostly topic 0 but holds two topic-1 misfits
        a_members = [
            add_section(conn, f"a{i}\n".encode(), unit(0)) for i in range(4)
        ]
        strays = [
            add_section(conn, f"m{i}\n".encode(), unit(1)) for i in range(2)
        ]
        node_a = node_of(conn, a_members + strays)
        node_b = node_of(
            conn,
            [add_section(conn, f"b{i}\n".encode(), unit(1)) for i in range(4)],
        )
    with db.connect() as conn, conn:
        moved = repair.migrate(conn, TREE, node_a, MODEL)
    assert moved == 2
    with db.connect() as conn:
        for stray in strays:
            assert cluster_store.section_node(conn, TREE, stray) == node_b
        # the on-topic members stayed put
        for member in a_members:
            assert cluster_store.section_node(conn, TREE, member) == node_a


def test_dissolve_retires_a_below_two_cluster(db: Database) -> None:
    with db.connect() as conn, conn:
        node_of(
            conn,
            [add_section(conn, f"a{i}\n".encode(), unit(0)) for i in range(3)],
        )
        # a lone topic-0 member in its own node -> re-places into topic-0 node
        loner = add_section(conn, b"lone topic 0\n", unit(0))
        tiny = node_of(conn, [loner])
    with db.connect() as conn, conn:
        assert repair.dissolve(conn, TREE, tiny, MODEL, batch=1) is True
    with db.connect() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM nodes WHERE id = ?", (tiny,)
            ).fetchone()[0]
            == 0
        )  # node retired
        assert (
            cluster_store.section_node(conn, TREE, loner) is not None
        )  # re-placed


def test_dissolve_parks_a_survivor_with_no_home(db: Database) -> None:
    with db.connect() as conn, conn:
        loner = add_section(conn, b"only topic 3\n", unit(3))
        tiny = node_of(
            conn, [loner]
        )  # the only cluster; nothing to re-place into
    with db.connect() as conn, conn:
        assert repair.dissolve(conn, TREE, tiny, MODEL, batch=1) is True
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 1  # parked


def _forced(conn: object, node_id: int, section_id: int) -> bool:
    return section_id in cluster_store.forced_members(conn, node_id)  # type: ignore[arg-type]


def test_a_forced_pioneer_leaves_once_its_real_siblings_form(
    db: Database,
) -> None:
    # #113 / F29: `docs/unrelated-cooking-notes.md` force-assigned at 0.281 into
    # a source-code topic. One alien member in seven is a rate of 0.14 — under
    # MISFIT_THRESHOLD — so the rate alone never triggers the repair that frees
    # it. The flag does.
    with db.connect() as conn, conn:
        members = [
            add_section(conn, f"code{i}\n".encode(), unit(0)) for i in range(6)
        ]
        pioneer = add_section(conn, b"cooking notes\n", unit(3))
        married = cluster_store.add_leaf_node(
            conn,
            TREE,
            [(s, False, None) for s in members] + [(pioneer, True, 0.281)],
        )
        siblings = [  # its real siblings finally form a cluster of their own
            add_section(conn, f"cooking{i}\n".encode(), unit(3))
            for i in range(3)
        ]
        home = node_of(conn, siblings)
        monitor.refresh(conn, TREE, MODEL, [married, home])

    with db.connect() as conn:
        assert monitor.cluster_rate(conn, TREE, married) < (
            repair.MISFIT_THRESHOLD
        )

    with db.connect() as conn, conn:
        repair.repair(_job(), job_context(db, Path(".")))

    with db.connect() as conn:
        assert cluster_store.section_node(conn, TREE, pioneer) == home
        assert not _forced(conn, home, pioneer)  # re-placed normally: flag gone


def test_a_forced_member_with_nowhere_better_stays_put(db: Database) -> None:
    # the repair must not shuffle a pioneer into a cluster that fits it worse
    # just because it is flagged: with no better home it keeps its place, and
    # keeps its flag, so the next batch looks again.
    with db.connect() as conn, conn:
        members = [
            add_section(conn, f"code{i}\n".encode(), unit(0)) for i in range(6)
        ]
        pioneer = add_section(conn, b"cooking notes\n", unit(3))
        married = cluster_store.add_leaf_node(
            conn,
            TREE,
            [(s, False, None) for s in members] + [(pioneer, True, 0.281)],
        )
        node_of(conn, [add_section(conn, b"other\n", unit(1))])
        monitor.refresh(conn, TREE, MODEL, [married])

    with db.connect() as conn, conn:
        repair.repair(_job(), job_context(db, Path(".")))

    with db.connect() as conn:
        assert cluster_store.section_node(conn, TREE, pioneer) == married
        assert _forced(conn, married, pioneer)
