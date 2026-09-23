import hashlib
import json
from collections.abc import Iterator

import pytest

from hrono.cluster import monitor, repair
from hrono.cluster import store as cluster_store
from hrono.cluster.levels import (
    _sole_ancestor,
    attach_orphans,
    cluster_briefs,
    migrate_children,
    upper_misfits,
)
from hrono.cluster.placement import TAU
from hrono.db.database import Database
from hrono.embed.store import upsert_vector
from hrono.ingest.identity import content_hash
from hrono.ingest.store import upsert_content
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
                member_signature="sig",
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
    database = Database.at(tmp_path / "hrono.db")
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
    # each recovered cluster is a single planted group (label order is the
    # clusterer's business, so compare the partition as a set)
    assert set(_partition(db, node_group)) == {
        frozenset({"alpha"}),
        frozenset({"beta"}),
    }


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
        database = Database.at(tmp_path / f"{name}.db")
        with database.connect() as conn, conn:
            register_embedding_model(conn)
            node_group = build_level0(conn)
        cluster_briefs(
            job(), JobContext(database), encoder_for=fake_encoder_for([])
        )
        groups.append(sorted(_partition(database, node_group)))
        database.close()
    assert groups[0] == groups[1]


def _new_leaf(conn: object, text: str) -> int:
    cursor = conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO nodes(tree, level, label, created_at) "
        "VALUES ('default', 0, -1, 't')"
    )
    node_id = int(cursor.lastrowid)
    briefs.upsert(
        conn,  # type: ignore[arg-type]
        node_id,
        text,
        model_name="emb",
        prompt_name="brief",
        prompt_hash="h",
        member_signature="sig",
        input_tokens=1,
        output_tokens=1,
    )
    return node_id


def _parent_of(db: Database, child: int) -> tuple[int | None, float | None]:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT parent_id, assignment_similarity AS sim, attached "
            "FROM node_children WHERE child_id = ?",
            (child,),
        ).fetchone()
    return (None, None) if row is None else (int(row["parent_id"]), row["sim"])


def _group_of_parent(db: Database, parent: int, groups: dict[int, str]) -> str:
    with db.connect() as conn:
        children = [
            int(r["child_id"])
            for r in conn.execute(
                "SELECT child_id FROM node_children WHERE parent_id = ? "
                "AND child_id IN (SELECT id FROM nodes WHERE level = 0)",
                (parent,),
            ).fetchall()
        ]
    named = [groups[c] for c in children if c in groups]
    return max(set(named), key=named.count)


def test_a_late_leaf_is_attached_to_the_nearest_parent(
    seeded: tuple[Database, dict[int, str]],
) -> None:
    # #114: a leaf the incubator emitted after build_tree recursed has no
    # parent, so root.md — whose children are rendered from parent edges —
    # never links it. It joins the topic its BRIEF is nearest to.
    db, groups = seeded
    encoder = fake_encoder_for([])
    cluster_briefs(job(), JobContext(db), encoder_for=encoder)
    with db.connect() as conn, conn:
        late = _new_leaf(conn, "beta topic number 99")

    attached = attach_orphans(job(), JobContext(db), encoder_for=encoder)

    assert [child for child, _, _ in attached] == [late]
    parent, similarity = _parent_of(db, late)
    assert parent is not None
    assert _group_of_parent(db, parent, groups) == "beta"
    assert similarity is not None and similarity >= TAU
    with db.connect() as conn:
        row = conn.execute(
            "SELECT attached FROM node_children WHERE child_id = ?", (late,)
        ).fetchone()
    # a confident placement is NOT "attached by proximity" (0009_nodes.sql),
    # and #114 records its similarity anyway — node_children keeps the score on
    # every row, unlike node_members.
    assert int(row["attached"]) == 0


def test_a_leaf_that_fits_nowhere_is_still_attached(
    seeded: tuple[Database, dict[int, str]],
) -> None:
    # parking is not available one level up: a node under no parent is
    # unreachable, which is worse than an imperfect parent. It lands on the
    # nearest one with attached=0 so the monitor/settle path can see it.
    db, _ = seeded

    def three_way(model_id: str):
        def encode(texts: list[str]) -> list[list[float]]:
            out = []
            for text in texts:
                base = [0.0] * DIMS
                base[
                    2 if "gamma" in text else (0 if "alpha" in text else 1)
                ] = 1.0
                out.append(base)
            return out

        return encode

    cluster_briefs(job(), JobContext(db), encoder_for=three_way)
    with db.connect() as conn, conn:
        late = _new_leaf(conn, "gamma unrelated material entirely")

    attach_orphans(job(), JobContext(db), encoder_for=three_way)

    parent, similarity = _parent_of(db, late)
    assert parent is not None
    with db.connect() as conn:
        row = conn.execute(
            "SELECT attached FROM node_children WHERE child_id = ?", (late,)
        ).fetchone()
    # 0009_nodes.sql: 1 = attached by PROXIMITY, 0 = a confident core member
    assert int(row["attached"]) == 1
    assert similarity is not None and similarity < TAU


def test_attaching_refreshes_the_parents_signature_and_staleness(
    seeded: tuple[Database, dict[int, str]],
) -> None:
    # the parent gained a child, so #068 must still match it to itself at the
    # next rebuild and #064 must see its brief as stale — a parent brief that
    # omits the topic underneath it is this ticket's harm one level up.
    db, _ = seeded
    encoder = fake_encoder_for([])
    cluster_briefs(job(), JobContext(db), encoder_for=encoder)
    with db.connect() as conn, conn:
        late = _new_leaf(conn, "beta topic number 98")
    attach_orphans(job(), JobContext(db), encoder_for=encoder)

    parent, _ = _parent_of(db, late)
    assert parent is not None
    with db.connect() as conn:
        stored = conn.execute(
            "SELECT signature FROM nodes WHERE id = ?", (parent,)
        ).fetchone()["signature"]
        assert stored == cluster_store.node_child_signature(conn, parent)
        assert briefs.member_signature(conn, parent) != "sig"


def test_attach_is_a_no_op_while_the_tree_is_a_single_level(
    seeded: tuple[Database, dict[int, str]],
) -> None:
    # normal for a small corpus: build_tree's _collect_root gives it a root
    # before there is anything to be reachable from.
    db, _ = seeded
    assert (
        attach_orphans(job(), JobContext(db), encoder_for=fake_encoder_for([]))
        == ()
    )
    with db.connect() as conn:
        assert (
            conn.execute("SELECT COUNT(*) FROM node_children").fetchone()[0]
            == 0
        )


def test_a_leaf_with_no_brief_is_left_for_the_next_brief_pass(
    seeded: tuple[Database, dict[int, str]],
) -> None:
    # the update path: its drain emits leaves and update never briefs, so there
    # is no vector to place them by until a brief pass runs.
    db, _ = seeded
    encoder = fake_encoder_for([])
    cluster_briefs(job(), JobContext(db), encoder_for=encoder)
    with db.connect() as conn, conn:
        cursor = conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES ('default', 0, -1, 't')"
        )
        unbriefed = int(cursor.lastrowid)

    assert attach_orphans(job(), JobContext(db), encoder_for=encoder) == ()
    assert _parent_of(db, unbriefed) == (None, None)


TREE = "default"
MODEL = "emb"
_TOPICS = {"alpha": 0, "beta": 1, "gamma": 2}


def _leaf(conn: object, topic: str, i: int) -> int:
    """A level-0 node whose brief text is embedded on ``topic``'s axis."""
    text = f"{topic} topic number {i}"
    cursor = conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO nodes(tree, level, label, created_at) "
        "VALUES (?, 0, 0, 't')",
        (TREE,),
    )
    node_id = int(cursor.lastrowid)
    briefs.upsert(
        conn,  # type: ignore[arg-type]
        node_id,
        text,
        model_name=MODEL,
        prompt_name="brief",
        prompt_hash="h",
        member_signature="sig",
        input_tokens=1,
        output_tokens=1,
    )
    body = text.encode("utf-8")
    upsert_content(conn, content_hash(body), body)  # type: ignore[arg-type]
    vector = [0.0] * DIMS
    vector[_TOPICS[topic]] = 1.0
    upsert_vector(conn, content_hash(body), MODEL, vector)  # type: ignore[arg-type]
    return node_id


def _parent(conn: object, children: list[int]) -> int:
    cursor = conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO nodes(tree, level, label, created_at) "
        "VALUES (?, 1, 0, 't')",
        (TREE,),
    )
    parent_id = int(cursor.lastrowid)
    for child in children:
        cluster_store.add_child(
            conn,  # type: ignore[arg-type]
            parent_id,
            child,
            attached=False,
            similarity=None,
        )
    return parent_id


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_embedding_model(conn)
    yield database
    database.close()


def _mis_attached(
    db: Database, with_a_better_home: bool
) -> tuple[int, int, int | None]:
    """#114's real shape: a gamma leaf attached under the alpha parent.

    The attach went to the NEAREST parent and the centroid then absorbed it, so
    `own` (0.45) beats every `best_other` — the level-0 rule is blind to it,
    which is the whole point of #123. Returns (alpha parent, stray, gamma home).
    """
    with db.connect() as conn, conn:
        alpha = _parent(conn, [_leaf(conn, "alpha", i) for i in range(2)])
        _parent(conn, [_leaf(conn, "beta", i) for i in range(2)])
        stray = _leaf(conn, "gamma", 0)
        cluster_store.add_child(
            conn, alpha, stray, attached=True, similarity=0.281
        )
        home = (
            _parent(conn, [_leaf(conn, "gamma", i) for i in (1, 2)])
            if with_a_better_home
            else None
        )
    return alpha, stray, home


def test_a_below_tau_attached_child_is_a_misfit_of_its_parent(
    db: Database,
) -> None:
    # #123: #114 attaches an orphan to its NEAREST parent and the parent's
    # centroid then absorbs it, so `best_other > own` can never fire for the
    # placements this exists to review — exactly as a force-assigned member is
    # invisible to the level-0 rule (#113).
    alpha, _stray, _home = _mis_attached(db, with_a_better_home=False)

    with db.connect() as conn:
        rows = upper_misfits(conn, TREE, 1, MODEL)
    by_parent = {node_id: (m, c) for node_id, m, c in rows}

    assert by_parent[alpha] == (1, 3)  # the stray, out of three children
    assert [m for p, (m, _) in by_parent.items() if p != alpha] == [0]


def test_the_same_child_unattached_is_not_a_misfit(db: Database) -> None:
    # the control: identical vectors, identical geometry, flag off. It is the
    # FLAG that is read — the stray is nearest to this parent either way, so
    # the `best_other > own` rule still says nothing about it.
    with db.connect() as conn, conn:
        alpha = _parent(conn, [_leaf(conn, "alpha", i) for i in range(2)])
        _parent(conn, [_leaf(conn, "beta", i) for i in range(2)])
        stray = _leaf(conn, "gamma", 0)
        cluster_store.add_child(
            conn, alpha, stray, attached=False, similarity=0.281
        )

    with db.connect() as conn:
        rows = upper_misfits(conn, TREE, 1, MODEL)

    assert {m for _p, m, _c in rows} == {0}


def test_an_attached_child_that_actually_fits_is_not_a_misfit(
    db: Database,
) -> None:
    # attaching is not guilt: a child attached at or above TAU has nothing to
    # correct and must not inflate its parent's rate for ever.
    with db.connect() as conn, conn:
        alpha = _parent(conn, [_leaf(conn, "alpha", i) for i in range(2)])
        _parent(conn, [_leaf(conn, "beta", i) for i in range(2)])
        close = _leaf(conn, "alpha", 9)
        cluster_store.add_child(
            conn, alpha, close, attached=True, similarity=0.99
        )

    with db.connect() as conn:
        rows = upper_misfits(conn, TREE, 1, MODEL)

    assert {m for _p, m, _c in rows} == {0}


def test_a_mis_attached_child_moves_once_a_better_parent_exists(
    db: Database,
) -> None:
    alpha, stray, home = _mis_attached(db, with_a_better_home=True)

    with db.connect() as conn, conn:
        moved = migrate_children(conn, TREE, 1, MODEL)

    assert moved == 1
    with db.connect() as conn:
        row = conn.execute(
            "SELECT parent_id, attached FROM node_children WHERE child_id = ?",
            (stray,),
        ).fetchone()
    assert int(row["parent_id"]) == home  # the parent it belongs under
    assert int(row["parent_id"]) != alpha
    assert int(row["attached"]) == 0  # re-parented normally: flag cleared


def test_a_child_with_nowhere_better_keeps_its_place_and_its_flag(
    db: Database,
) -> None:
    # the repair must not shuffle a child into a parent that fits it worse just
    # because it is flagged: with no better home it keeps both, and the next
    # pass looks again.
    alpha, stray, _home = _mis_attached(db, with_a_better_home=False)

    with db.connect() as conn, conn:
        moved = migrate_children(conn, TREE, 1, MODEL)

    assert moved == 0
    with db.connect() as conn:
        row = conn.execute(
            "SELECT parent_id, attached FROM node_children WHERE child_id = ?",
            (stray,),
        ).fetchone()
    assert (int(row["parent_id"]), int(row["attached"])) == (alpha, 1)


def test_a_move_restales_both_parents_briefs(db: Database) -> None:
    # a parent's brief is written over its CHILDREN, so both the parent that
    # lost one and the parent that gained one must re-brief (#064 reads the
    # child-id signature). That is the harm #123 exists to stop: a badly
    # attached child pollutes its parent's brief content.
    alpha, stray, home = _mis_attached(db, with_a_better_home=True)
    with db.connect() as conn:
        before = {
            p: conn.execute(
                "SELECT signature FROM nodes WHERE id = ?", (p,)
            ).fetchone()["signature"]
            for p in (alpha, home)
        }

    with db.connect() as conn, conn:
        migrate_children(conn, TREE, 1, MODEL)

    with db.connect() as conn:
        after = {
            p: conn.execute(
                "SELECT signature FROM nodes WHERE id = ?", (p,)
            ).fetchone()["signature"]
            for p in (alpha, home)
        }
    assert after[alpha] != before[alpha]  # lost a child
    assert after[home] != before[home]  # gained one


def _monitor_job() -> Job:
    return Job(
        id="mon",
        parent_id=None,
        tree=TREE,
        op="monitor",
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


def _repair_job() -> Job:
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


def test_the_monitor_op_stores_the_upper_level_count(db: Database) -> None:
    # criterion 1 driven through the op, not the helper: the signal has to be
    # observable in the monitor's stored counts, which is what repair and
    # settle read — not only in a column nothing selects.
    alpha, _stray, _home = _mis_attached(db, with_a_better_home=False)

    monitor.monitor(_monitor_job(), JobContext(db))

    with db.connect() as conn:
        row = conn.execute(
            "SELECT misfits, members FROM misfit "
            "WHERE tree = ? AND node_id = ?",
            (TREE, alpha),
        ).fetchone()
        rate = monitor.cluster_rate(conn, TREE, alpha)
    assert (int(row["misfits"]), int(row["members"])) == (1, 3)
    assert rate > 0.0


def test_the_repair_op_frees_a_mis_attached_child(db: Database) -> None:
    # criterion 2 driven through the op: one badly attached child in three is a
    # rate of 0.33 here, but the trigger must not depend on the rate — #114
    # attaches to the NEAREST parent, so a larger parent hides it entirely.
    alpha, stray, home = _mis_attached(db, with_a_better_home=True)

    repair.repair(_repair_job(), JobContext(db))

    with db.connect() as conn:
        row = conn.execute(
            "SELECT parent_id, attached FROM node_children WHERE child_id = ?",
            (stray,),
        ).fetchone()
    assert int(row["parent_id"]) == home
    assert int(row["parent_id"]) != alpha
    assert int(row["attached"]) == 0


def _childless_upper(conn: object, level: int, count: int) -> list[int]:
    ids = []
    for _ in range(count):
        cursor = conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, ?, 0, 't')",
            (TREE, level),
        )
        ids.append(int(cursor.lastrowid))
    return ids


def test_orphans_collect_one_level_up_when_every_parent_is_childless(
    db: Database,
) -> None:
    # #124: #114 handles ONE childless parent. With several there is no
    # centroid to place by and no single node to collect under, and the driven
    # result was the whole corpus written to the export and linked from
    # nothing. A level whose every node lost its children carries no
    # information; the node above it does.
    with db.connect() as conn, conn:
        leaves = [_leaf(conn, "alpha", i) for i in range(3)]
        _childless_upper(conn, 1, 2)  # TWO childless candidate parents
        root = _childless_upper(conn, 2, 1)[0]

    attached = attach_orphans(
        Job(
            id="ao",
            parent_id=None,
            tree=TREE,
            op="attach-orphans",
            scope={},
            status="running",
            error=None,
            created_at="t",
            updated_at="t",
        ),
        JobContext(db),
        encoder_for=fake_encoder_for([]),
    )

    assert {child for child, _p, _s in attached} == set(leaves)
    assert {parent for _c, parent, _s in attached} == {root}
    with db.connect() as conn:
        assert cluster_store.unparented(conn, TREE, 0) == ()


def test_the_ancestor_search_skips_a_level_that_offers_a_choice(
    db: Database,
) -> None:
    # #124: collecting orphans is only safe under a node that is the ONLY
    # candidate. A level holding several is a choice, and picking one of them
    # arbitrarily buries the orphans under a topic nothing says they belong to.
    with db.connect() as conn, conn:
        _childless_upper(conn, 1, 2)  # a choice: skip it
        sole = _childless_upper(conn, 2, 1)[0]  # the only candidate: take it

    assert _sole_ancestor(JobContext(db), TREE, 0) == [sole]


def test_repair_reports_the_children_it_reparented(db: Database) -> None:
    # #133: `reparented` is `freed` one level up — a child #123 moved out of a
    # parent it was attached below TAU into. Without a value assertion the
    # count could be pinned at zero and the operator would never learn that the
    # map's shape changed underneath them.
    _alpha, _stray, _home = _mis_attached(db, with_a_better_home=True)

    outcome = repair.repair(_repair_job(), JobContext(db))

    assert outcome["reparented"] == 1
