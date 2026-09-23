"""T35: the incubator pending pool — park, drain, force-assign, aging."""

from collections.abc import Iterator
from threading import Thread

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
from tests.cluster.invariant import assert_pool_invariant

MODEL = "emb"
DIMS = 4
PATH = "src/x.py"
TREE = "default"


def unit(i: int) -> list[float]:
    v = [0.0] * DIMS
    v[i] = 1.0
    return v


def add_section(
    conn: object, body: bytes, content_vec: list[float], path: str = PATH
) -> int:
    """Store a section (content embedded) and return its SECTION id."""
    digest = content_hash(body)
    upsert_content(conn, digest, body)  # type: ignore[arg-type]
    upsert_vector(conn, digest, MODEL, content_vec)  # type: ignore[arg-type]
    return insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "ex/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )


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
        cluster_store.add_leaf_node(conn, TREE, [(existing, False, None)])
    yield database
    database.close()


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
        section_id = add_section(conn, b"parked\n", unit(1))
        incubator.park(conn, TREE, section_id, batch=1)
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 1
        assert incubator.pending(conn, TREE) == (
            (section_id, content_hash(b"parked\n"), PATH, 1),
        )
    with db.connect() as conn, conn:
        incubator.unpark(conn, TREE, section_id)
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 0


def test_a_re_park_keeps_the_original_wait(db: Database) -> None:
    # ON CONFLICT DO NOTHING: re-parking the same section must not restart its
    # age clock (a plain INSERT would raise, an upsert would reset the batch).
    with db.connect() as conn, conn:
        section_id = add_section(conn, b"parked twice\n", unit(1))
        incubator.park(conn, TREE, section_id, batch=1)
        incubator.park(conn, TREE, section_id, batch=7)
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 1
        assert incubator.pending(conn, TREE)[0][3] == 1


def test_below_min_does_not_drain(db: Database) -> None:
    with db.connect() as conn, conn:
        for i in range(3):
            d = add_section(conn, f"c{i}\n".encode(), unit(1))
            incubator.park(conn, TREE, d, batch=1)
    assert incubator.drain(db, TREE, MODEL) is False
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 3  # still pending


def test_drain_emits_cores_and_force_assigns_residual(db: Database) -> None:
    existing_node = 1  # the fixture's only node
    with db.connect() as conn, conn:
        for i in range(MIN_POINTS - 1):  # e1 chunks -> one density core
            d = add_section(conn, f"core{i}\n".encode(), unit(1))
            incubator.park(conn, TREE, d, batch=1)
        residual = add_section(conn, b"residual\n", unit(0))  # near existing
        incubator.park(conn, TREE, residual, batch=1)
    assert incubator.drain(db, TREE, MODEL, core_labeler=content_core_labeler)
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
        incubator.park(conn, TREE, old, batch=1)
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
        incubator.park(conn, TREE, d, batch=8)
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
            incubator.park(conn, TREE, d, batch=1)
    assert incubator.drain(db, TREE, MODEL) is False
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
        cluster_store.add_leaf_node(conn, TREE, [(existing, False, None)])
        for i, vector in enumerate(vectors):
            section_id = add_section(
                conn, f"planted {i}\n".encode(), [float(v) for v in vector]
            )
            incubator.park(conn, TREE, section_id, batch=1)
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
    assert incubator.drain(planted, TREE, MODEL) is True
    with planted.connect() as conn:
        assert incubator.count(conn, TREE) == 0
    assert _level0(planted) == before + 2  # both planted groups became nodes
    assert _log(planted).count(("drain", "core")) == 2


def test_drain_and_age_are_written_to_the_update_log(db: Database) -> None:
    with db.connect() as conn, conn:
        old = add_section(conn, b"old pending\n", unit(0))
        incubator.park(conn, TREE, old, batch=1)
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
            body = f"blind{i}\n".encode()
            incubator.park(conn, TREE, add_section(conn, body, unit(0)), 1)
            conn.execute(
                "DELETE FROM embeddings WHERE content_hash = ?",
                (content_hash(body),),
            )
        placeable = add_section(conn, b"placeable\n", unit(0))
        incubator.park(conn, TREE, placeable, batch=1)
    with db.connect() as conn, conn:
        assert incubator.age(conn, TREE, MODEL, current_batch=10) == 1
    with db.connect() as conn:
        assert incubator.pending(conn, TREE) and all(
            entry[0] != placeable for entry in incubator.pending(conn, TREE)
        )
    # the rows that stay are UNPLACEABLE (no vector at all), the one bound the
    # invariant's time limit carries: ageing rescued everything it could.
    assert_pool_invariant(db, TREE, MODEL)


def test_sweep_retires_pool_rows_a_rebuild_has_already_homed(
    db: Database,
) -> None:
    with db.connect() as conn, conn:
        section_id = add_section(conn, b"rehomed\n", unit(1))
        incubator.park(conn, TREE, section_id, batch=1)
        cluster_store.add_member(
            conn, 1, section_id, forced=False, similarity=0.9
        )
    with db.connect() as conn, conn:
        assert incubator.sweep(conn, TREE) == 1
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 0


def test_sweep_leaves_a_genuinely_homeless_chunk_alone(db: Database) -> None:
    with db.connect() as conn, conn:
        section_id = add_section(conn, b"homeless\n", unit(1))
        incubator.park(conn, TREE, section_id, batch=1)
    with db.connect() as conn, conn:
        assert incubator.sweep(conn, TREE) == 0
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 1


TWIN_PATH = "docs/x.py"


def _twins(conn: object) -> tuple[int, int]:
    """Two sections with the SAME body at different paths (#095).

    Identical content, so one content hash — but the #039 path blend gives them
    different combined vectors, so one can be homed while the other is parked.
    """
    register_path_bodies(conn, [TWIN_PATH])  # type: ignore[arg-type]
    upsert_vector(
        conn,  # type: ignore[arg-type]
        content_hash(path_body(TWIN_PATH)),
        MODEL,
        unit(3),
    )
    body = b"the very same body\n"
    return (
        add_section(conn, body, unit(1)),
        add_section(conn, body, unit(1), path=TWIN_PATH),
    )


def test_sweep_keeps_the_row_of_a_twin_the_rebuild_did_not_home(
    db: Database,
) -> None:
    # same content hash, one homed and one parked: a hash-keyed sweep retires
    # the row and strands the parked twin in NO node and NO pool.
    with db.connect() as conn, conn:
        homed, parked = _twins(conn)
        cluster_store.add_member(conn, 1, homed, forced=False, similarity=0.9)
        incubator.park(conn, TREE, parked, batch=1)
    with db.connect() as conn, conn:
        assert incubator.sweep(conn, TREE) == 0
    with db.connect() as conn:
        assert incubator.pending(conn, TREE)[0][0] == parked
    assert_pool_invariant(db, TREE, MODEL)


def test_ageing_forces_only_the_parked_twin(db: Database) -> None:
    # the parked twin's nearest centroid is a node its homed twin is NOT in, so
    # force-assigning by content hash drags the homed one into a SECOND node.
    with db.connect() as conn, conn:
        homed, parked = _twins(conn)
        neighbour = add_section(
            conn, b"same neighbourhood\n", unit(1), path=TWIN_PATH
        )
        target = cluster_store.add_leaf_node(
            conn, TREE, [(neighbour, False, None)]
        )
        cluster_store.add_member(conn, 1, homed, forced=False, similarity=0.9)
        incubator.park(conn, TREE, parked, batch=1)
    with db.connect() as conn, conn:
        assert incubator.age(conn, TREE, MODEL, current_batch=10) == 1
    with db.connect() as conn:
        assert incubator.count(conn, TREE) == 0
        forced = conn.execute(
            "SELECT node_id, section_id FROM node_members WHERE forced = 1"
        ).fetchall()
        assert [
            (int(row["node_id"]), int(row["section_id"])) for row in forced
        ] == [(target, parked)]
    assert_pool_invariant(db, TREE, MODEL)


def _write_from_another_thread(db: Database, done: list[bool]) -> None:
    with db.write() as conn:
        conn.execute("INSERT INTO tree_batch(tree, batch) VALUES ('p', 1)")
    done.append(True)


def test_drain_labels_the_pool_off_the_write_lock(planted: Database) -> None:
    # the mini-pipeline is real UMAP -> HDBSCAN; the module's lock discipline
    # says heavy compute runs outside the #008 lock, so another thread must be
    # able to take the write lock while the pool is being labelled.
    done: list[bool] = []

    def labeler(vectors: object) -> list[int]:
        thread = Thread(
            target=_write_from_another_thread, args=(planted, done), daemon=True
        )
        thread.start()
        thread.join(timeout=5)
        return [0] * len(vectors)  # type: ignore[arg-type]

    assert incubator.drain(planted, TREE, MODEL, core_labeler=labeler) is True
    assert done == [True]


def test_a_section_homed_mid_drain_is_not_homed_twice(db: Database) -> None:
    # #115: the pool is read under the read door and the clustering runs off
    # the lock, so the write block acts on a SNAPSHOT. Trusting it writes a
    # second level-0 membership for any section that found a home in between —
    # the "is in 2 nodes" half of the #086 invariant, in a tree nobody touched.
    with db.connect() as conn, conn:
        parked = [
            add_section(conn, f"core{i}\n".encode(), unit(1))
            for i in range(MIN_POINTS)
        ]
        for section_id in parked:
            incubator.park(conn, TREE, section_id, batch=1)

    stolen = parked[0]

    def labeler_that_homes_one(vectors: object) -> list[int]:
        # something else places `stolen` while this drain is computing
        with db.connect() as conn, conn:
            incubator.unpark(conn, TREE, stolen)
            cluster_store.add_member(
                conn, 1, stolen, forced=False, similarity=0.9
            )
        return content_core_labeler(vectors)

    incubator.drain(db, TREE, MODEL, core_labeler=labeler_that_homes_one)

    with db.connect() as conn:
        homes = conn.execute(
            "SELECT COUNT(*) FROM node_members m JOIN nodes n "
            "ON n.id = m.node_id WHERE n.level = 0 AND m.section_id = ?",
            (stolen,),
        ).fetchone()[0]
    assert homes == 1  # exactly one level-0 node, not two


def test_a_drain_whose_pool_empties_mid_run_writes_nothing(
    db: Database,
) -> None:
    # the degenerate case of the same race: every section finds a home while
    # the clustering runs, so there is nothing left to persist.
    with db.connect() as conn, conn:
        parked = [
            add_section(conn, f"core{i}\n".encode(), unit(1))
            for i in range(MIN_POINTS)
        ]
        for section_id in parked:
            incubator.park(conn, TREE, section_id, batch=1)
    before = _node_count(db)

    def labeler_that_empties_the_pool(vectors: object) -> list[int]:
        with db.connect() as conn, conn:
            for section_id in parked:
                incubator.unpark(conn, TREE, section_id)
        return content_core_labeler(vectors)

    incubator.drain(db, TREE, MODEL, core_labeler=labeler_that_empties_the_pool)

    assert _node_count(db) == before  # no node minted for a pool that is gone


def _node_count(db: Database) -> int:
    with db.connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0])


def test_a_residual_homed_mid_drain_is_not_force_assigned(
    db: Database,
) -> None:
    # #115's other half: a residual takes the force-assign path, not the core
    # path, and it needs the same re-check. A section homed while the drain
    # computes would be force-assigned on top of the home it already found —
    # and flagged `forced`, so #113 would later "free" a pioneer that never was.
    with db.connect() as conn, conn:
        for i in range(MIN_POINTS - 1):
            section_id = add_section(conn, f"core{i}\n".encode(), unit(1))
            incubator.park(conn, TREE, section_id, batch=1)
        residual = add_section(conn, b"residual\n", unit(0))
        incubator.park(conn, TREE, residual, batch=1)

    def labeler_that_homes_the_residual(vectors: object) -> list[int]:
        # homed into a DIFFERENT node than the force-assign would pick —
        # `_insert_member` is INSERT OR IGNORE, so a second membership in the
        # SAME node is silently absorbed and would hide the defect.
        with db.connect() as conn, conn:
            incubator.unpark(conn, TREE, residual)
            elsewhere = add_section(conn, b"elsewhere\n", unit(2))
            cluster_store.add_leaf_node(
                conn, TREE, [(elsewhere, False, None), (residual, False, None)]
            )
        return content_core_labeler(vectors)

    incubator.drain(
        db, TREE, MODEL, core_labeler=labeler_that_homes_the_residual
    )

    with db.connect() as conn:
        homes = conn.execute(
            "SELECT COUNT(*) FROM node_members m JOIN nodes n "
            "ON n.id = m.node_id WHERE n.level = 0 AND m.section_id = ?",
            (residual,),
        ).fetchone()[0]
        forced = conn.execute(
            "SELECT COUNT(*) FROM node_members WHERE forced = 1 "
            "AND section_id = ?",
            (residual,),
        ).fetchone()[0]
    assert homes == 1  # the home it already found, not a second one
    assert forced == 0  # and not mis-flagged as a forced pioneer
