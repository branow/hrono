"""T37: the misfit-rate monitor — exact rate, incremental, baseline-relative."""

from collections.abc import Iterator

import pytest

from hrono.cluster import monitor
from hrono.cluster import store as cluster_store
from hrono.cluster.blend import path_body, register_path_bodies
from hrono.db.database import Database, open_database
from hrono.embed.store import upsert_vector
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.registry import store as registry_store

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


def make_node(conn: object, topic: int, extra: list[int]) -> int:
    """A cluster of ``topic`` members plus one member per ``extra`` vector."""
    members = [
        add_section(conn, f"t{topic}-{i}\n".encode(), unit(topic))
        for i in range(3)
    ]
    for j, v in enumerate(extra):
        members.append(add_section(conn, f"t{topic}-x{j}\n".encode(), unit(v)))
    return cluster_store.add_leaf_node(
        conn, TREE, [(s, False, None) for s in members]
    )


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database(open_database(tmp_path / "hrono.db"))  # type: ignore[operator]
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


def _job(dirty: list[int] | None = None) -> Job:
    return Job(
        id="mon",
        parent_id=None,
        tree=TREE,
        op="monitor",
        scope={"dirty": dirty or []},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


def test_registered() -> None:
    assert "monitor" in OPS


def test_exact_misfit_rate_global_and_per_cluster(db: Database) -> None:
    with db.connect() as conn, conn:
        # A is topic 0 but carries one topic-1 member (a planted misfit)
        node_a = make_node(conn, topic=0, extra=[1])
        node_b = make_node(conn, topic=1, extra=[])
    with db.connect() as conn, conn:
        monitor.refresh(conn, TREE, MODEL, [node_a, node_b])
    with db.connect() as conn:
        # A: 1 misfit of 4 members; B: 0 of 3; global 1/7
        assert monitor.cluster_rate(conn, TREE, node_a) == pytest.approx(1 / 4)
        assert monitor.cluster_rate(conn, TREE, node_b) == 0.0
        assert monitor.global_rate(conn, TREE) == pytest.approx(1 / 7)


def test_refresh_is_incremental(db: Database) -> None:
    with db.connect() as conn, conn:
        node_a = make_node(conn, topic=0, extra=[])
        node_b = make_node(conn, topic=1, extra=[])
        monitor.refresh(conn, TREE, MODEL, [node_a, node_b])
    # both clean now; make B misfit-heavy but only refresh A
    with db.connect() as conn, conn:
        stray = add_section(conn, b"stray topic 0 in b\n", unit(0))
        cluster_store.add_member(
            conn, node_b, stray, forced=False, similarity=None
        )
        monitor.refresh(conn, TREE, MODEL, [node_a])
    with db.connect() as conn:
        # B was NOT re-checked, so its stored count stays stale (still 0/3)
        assert monitor.cluster_rate(conn, TREE, node_b) == 0.0
    # refreshing B now picks up the misfit
    with db.connect() as conn, conn:
        monitor.refresh(conn, TREE, MODEL, [node_b])
    with db.connect() as conn:
        assert monitor.cluster_rate(conn, TREE, node_b) > 0.0


def test_sample_is_deterministic_and_bounded() -> None:
    nodes = [10, 20, 30, 40, 50]
    first = monitor.sample(nodes, exclude=[20], k=2, seed=7)
    assert first == monitor.sample(nodes, exclude=[20], k=2, seed=7)
    assert len(first) == 2
    assert 20 not in first  # excluded (dirty) never sampled
    assert set(monitor.sample(nodes, [], k=99, seed=0)) == set(nodes)  # bounded


def test_first_monitor_captures_baseline(db: Database) -> None:
    with db.connect() as conn, conn:
        make_node(conn, topic=0, extra=[1])  # one planted misfit
        make_node(conn, topic=1, extra=[])
    monitor.monitor(_job(), JobContext(db))
    with db.connect() as conn:
        base = monitor.baseline(conn, TREE)
        assert base is not None
        assert base == pytest.approx(monitor.global_rate(conn, TREE))
        assert base > 0.0
