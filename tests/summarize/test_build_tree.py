import json
from collections.abc import Callable, Iterator

import pytest

from hrono.cluster import ClusterError, TooFewPoints
from hrono.cluster import store as cluster_store
from hrono.cluster.build import ClusterResult
from hrono.db.database import Database
from hrono.export import store as export_store
from hrono.export.collapse import collapse
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.registry import store as registry_store
from hrono.summarize import UnreachableTree, briefs
from hrono.summarize.build_tree import (
    D_MAX,
    _adopt_late_leaves,
    _require_reachable,
    build_tree,
)

TREE = "default"


class FakeCompletion:
    def complete(self, request: CompletionRequest) -> CompletionResult:
        return CompletionResult(
            "This branch gathers the signing and serialization modules.",
            Usage(5, 2),
        )


def fake_encoder(model_id: str):
    def encode(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    return encode


def make_build(labels_of: Callable[[int], list[int]]):
    def build(vectors: object, *, init: object = None) -> ClusterResult:
        n = len(vectors)  # type: ignore[arg-type]
        labels = labels_of(n)
        return ClusterResult(
            labels=tuple(labels),
            attached=tuple(False for _ in range(n)),
            assignment_similarity=tuple(None for _ in range(n)),
            coords=tuple((0.0,) for _ in range(n)),
        )

    return build


def raising_build(vectors: object, *, init: object = None) -> ClusterResult:
    """The LADDER declining to reduce — a stop, not a failure."""
    raise TooFewPoints("too sparse")


def broken_build(vectors: object, *, init: object = None) -> ClusterResult:
    """The backend BREAKING — build_clusters raises this for four reasons."""
    raise ClusterError("the reduction failed on these vectors")


def register(conn: object) -> None:
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "models",
        "emb",
        json.dumps(
            {
                "name": "emb",
                "kind": "embedding",
                "connection": None,
                "model": "fake",
                "params": {"dims": 2, "batch_size": 8},
            }
        ),
        None,
        "t",
    )
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "models",
        "sonnet",
        json.dumps(
            {
                "name": "sonnet",
                "kind": "text",
                "connection": "c",
                "model": "claude",
                "params": {},
            }
        ),
        None,
        "t",
    )
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "prompts",
        "brief-upper",
        json.dumps(
            {
                "name": "brief-upper",
                "role": "brief-upper",
                "template": "Up {content}",
            }
        ),
        None,
        "t",
    )


def seed_leaves(conn: object, count: int) -> None:
    for i in range(count):
        cursor = conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES ('default', 0, ?, 't')",
            (i,),
        )
        briefs.upsert(
            conn,  # type: ignore[arg-type]
            int(cursor.lastrowid),
            f"leaf brief {i}",
            model_name="sonnet",
            prompt_name="brief",
            prompt_hash="h",
            member_signature=f"s{i}",
            input_tokens=1,
            output_tokens=1,
        )


def job() -> Job:
    return Job(
        id="bt",
        parent_id=None,
        tree=TREE,
        op="build-tree",
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    yield database
    database.close()


def _levels(db: Database) -> dict[int, int]:
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT level, COUNT(*) c FROM nodes GROUP BY level"
        ).fetchall()
    return {int(r["level"]): int(r["c"]) for r in rows}


def run(
    db: Database, labels_of: Callable[[int], list[int]] | None = None
) -> None:
    build = raising_build if labels_of is None else make_build(labels_of)
    build_tree(
        job(),
        JobContext(db),
        client=FakeCompletion(),
        encoder_for=fake_encoder,
        build=build,
    )


def test_build_tree_is_registered() -> None:
    assert "build-tree" in OPS


def test_recurses_to_a_single_root(db: Database) -> None:
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 12)
    run(db, lambda n: [i // 3 for i in range(n)])  # 12 -> 4 -> 2 -> 1
    levels = _levels(db)
    top = max(levels)
    assert levels[top] == 1  # a single root
    assert top >= 2  # genuinely multi-level
    # every level above the leaf has members that are the level below
    with db.connect() as conn:
        for level in range(1, top + 1):
            parents = conn.execute(
                "SELECT id FROM nodes WHERE level = ?", (level,)
            ).fetchall()
            for parent in parents:
                assert briefs.child_ids(conn, int(parent["id"]))


def _top_is_single_root(db: Database) -> None:
    """Every build must end with exactly one node at the top level."""
    levels = _levels(db)
    top = max(levels)
    assert levels[top] == 1
    with db.connect() as conn:
        root = int(
            conn.execute(
                "SELECT id FROM nodes WHERE level = ?", (top,)
            ).fetchone()["id"]
        )
        # the root's children are every node of the level below (all reachable)
        children = {
            int(r["child_id"])
            for r in conn.execute(
                "SELECT child_id FROM node_children WHERE parent_id = ?",
                (root,),
            ).fetchall()
        }
        below = {
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM nodes WHERE level = ?", (top - 1,)
            ).fetchall()
        }
    assert children == below and below  # no orphaned sibling top nodes


def test_non_reducing_top_is_collected_under_one_root(db: Database) -> None:
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 12)
    run(db, lambda n: list(range(n)))  # never reduces -> 12 stable top nodes
    _top_is_single_root(db)  # collected into one root, not left multi-top


def test_cluster_error_top_is_collected_under_one_root(db: Database) -> None:
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 12)
    run(db, None)  # raising build -> recursion stops immediately
    _top_is_single_root(db)


def test_depth_is_capped_at_d_max_then_a_root_collects_the_top(
    db: Database,
) -> None:
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 40)
    run(db, lambda n: [min(i, n - 2) for i in range(n)])  # reduce by one/level
    levels = _levels(db)
    # clustered levels are capped at D_MAX; the collect root sits one above it
    assert max(levels) == D_MAX + 1
    assert levels[D_MAX + 1] == 1  # single root
    assert levels[D_MAX] > 1  # the capped, non-reduced top it collects


def test_multi_top_export_is_complete_no_orphans(db: Database) -> None:
    # a multi-top stored tree would orphan sibling top nodes in export. With
    # the collected root, export sees one root and reaches all.
    from hrono.export.collapse import collapse
    from hrono.export.render import render
    from hrono.export.store import load

    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 12)
    run(db, lambda n: list(range(n)))  # 12 stable top nodes -> collected root
    with db.connect() as conn:
        stored = load(conn, "default")
        assert stored is not None
        files = render(conn, collapse(stored, 4))
    assert "root.md" in files
    assert not any(p.startswith("/") for p in files)  # no malformed "/brief.md"
    child_links = [
        ln for ln in files["root.md"].splitlines() if ln.startswith("- [")
    ]
    assert len(child_links) == 12  # every top topic reachable from root.md


def test_idempotent_second_run_adds_nothing(db: Database) -> None:
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 12)
    run(db, lambda n: [i // 3 for i in range(n)])
    first = _levels(db)
    run(db, lambda n: [i // 3 for i in range(n)])
    assert _levels(db) == first  # no duplicate levels, nothing rebuilt


def test_real_recipe_over_a_tiny_level_declares_a_root(db: Database) -> None:
    # the ladder end to end with the REAL clusterer (no build seam): 7 briefs
    # are below what UMAP can reduce, so cluster-briefs raises ClusterError,
    # recursion stops, and the 7 topics are collected under one root.
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 7)
    build_tree(
        job(),
        JobContext(db),
        client=FakeCompletion(),
        encoder_for=fake_encoder,
    )
    _top_is_single_root(db)
    levels = _levels(db)
    assert levels == {0: 7, 1: 1}


def test_a_broken_clusterer_fails_the_build_it_does_not_truncate(
    db: Database,
) -> None:
    # the declining-ladder rule one level down. `build_clusters` raises
    # ClusterError when the reduction fails, when the clusterer fails and
    # when the backend is missing — none of which mean
    # "the current top is the root". A tree that stops early and reports success
    # is a map an operator has no reason to distrust.
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 12)

    with pytest.raises(ClusterError):
        build_tree(
            job(),
            JobContext(db),
            client=FakeCompletion(),
            encoder_for=fake_encoder,
            build=broken_build,
        )


def test_the_ladder_declining_still_stops_the_climb(db: Database) -> None:
    # the behaviour that must NOT change: a level too sparse to reduce means
    # the current top is the root, and `TooFewPoints` is what says so.
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 12)

    run(db)  # raising_build -> TooFewPoints

    # no exception: the climb stopped and `_collect_root` parented the
    # survivors under one root, which is what "the current top is the root"
    # means in practice.
    assert _levels(db) == {0: 12, 1: 1}


def test_build_tree_refuses_to_report_success_over_an_unreachable_map(
    db: Database,
) -> None:
    # `root.md`'s children are rendered from parent EDGES, so an unparented
    # level-0 node is written to the export and unreachable in it. A build
    # must not report success over that map.
    #
    # Tested on the guard DIRECTLY, and deliberately: every route that produces
    # the state is closed (attach-by-proximity, the root collect), so the
    # normal flow repairs anything plantable here. This guard exists for the
    # routes nobody has thought of yet, which is exactly the kind a front-door
    # test cannot reach.
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 3)
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES ('default', 1, 0, 't')"
        )

    with pytest.raises(UnreachableTree, match="unreachable from the root"):
        _require_reachable(JobContext(db), "default")


def test_the_guard_sees_an_orphan_above_the_leaves(db: Database) -> None:
    """A detached SUBTREE must fail this guard, and it is the worse case.

    The orphan is an upper node, so its own children are parented — to it — and
    `unparented(level 0)` is empty. Checking only the leaves read a map with a
    branch hanging from nothing as a tidy one, and reported the build a
    success. Every level below the top now, for the same reason the level-0
    check existed at all.
    """
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 3)

        def node(level: int) -> int:
            cursor = conn.execute(
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES ('default', ?, 0, 't')",
                (level,),
            )
            return int(cursor.lastrowid)

        root, good, orphan = node(2), node(1), node(1)
        conn.execute(
            "INSERT INTO node_children(parent_id, child_id, attached, "
            "assignment_similarity, created_at) VALUES (?, ?, 0, NULL, 't')",
            (root, good),
        )
        for leaf in _leaf_ids(conn):
            conn.execute(
                "INSERT INTO node_children(parent_id, child_id, attached, "
                "assignment_similarity, created_at) "
                "VALUES (?, ?, 0, NULL, 't')",
                (orphan if leaf % 2 else good, leaf),
            )

    with db.connect() as conn:
        assert cluster_store.unparented(conn, "default", 0) == ()  # tidy below

    with pytest.raises(UnreachableTree, match="unreachable from the root"):
        _require_reachable(JobContext(db), "default")


def test_the_build_sweeps_every_level_for_orphans(db: Database) -> None:
    """The wiring, not the function.

    `attach_orphans(level=1)` is tested where it lives, and proving a function
    is not proving that anything calls it — the sweep here ran `range(1)` for
    its whole life and every unit test of the collector stayed green.
    """
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 4)

        def upper(level: int, label: int) -> int:
            cursor = conn.execute(
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES ('default', ?, ?, 't')",
                (level, label),
            )
            node = int(cursor.lastrowid)
            briefs.upsert(
                conn,
                node,
                f"upper brief {level}-{label}",
                model_name="sonnet",
                prompt_name="brief-upper",
                prompt_hash="h",
                member_signature=f"u{level}{label}",
                input_tokens=1,
                output_tokens=1,
            )
            return node

        root, good, orphan = upper(2, 0), upper(1, 0), upper(1, 1)
        leaves = _leaf_ids(conn)
        cluster_store.add_child(
            conn, root, good, attached=False, similarity=None
        )
        for i, leaf in enumerate(leaves):
            cluster_store.add_child(
                conn,
                orphan if i % 2 else good,
                leaf,
                attached=False,
                similarity=None,
            )

    with db.connect() as conn:
        assert cluster_store.unparented(conn, "default", 0) == ()
        assert orphan in cluster_store.unparented(conn, "default", 1)

    # the harm in the product's own terms: the export renders `root.md`'s
    # children from parent EDGES, so a node nothing points at is written and
    # unreachable. Three of these were -- the orphan and both its leaves.
    before = _export_reaches(db)
    assert orphan not in before
    assert set(leaves[1::2]).isdisjoint(before)

    _adopt_late_leaves(JobContext(db), TREE, FakeCompletion(), fake_encoder)

    with db.connect() as conn:
        assert cluster_store.unparented(conn, "default", 1) == ()
    _require_reachable(JobContext(db), TREE)  # and the guard agrees
    after = _export_reaches(db)
    assert {root, good, orphan, *leaves} <= after


def _export_reaches(db: Database) -> set[int]:
    """Every node the export actually renders, walked from its root.

    Not `unparented`, and deliberately: that reads the edge TABLE, while this
    reads what an agent is handed. `test_settle`'s existing helper walks every
    LEAF, which an upper orphan passes — its own leaves are parented, to it.
    """
    with db.connect() as conn:
        stored = export_store.load(conn, TREE)
    if stored is None:
        return set()
    tree = collapse(stored, 4)
    seen: set[int] = set()
    frontier = [tree.root]
    while frontier:
        node_id = frontier.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        node = tree.nodes.get(node_id)
        if node is not None:
            frontier.extend(node.children)
    return seen


def _leaf_ids(conn: object) -> list[int]:
    return [
        int(row["id"])
        for row in conn.execute(  # type: ignore[attr-defined]
            "SELECT id FROM nodes WHERE tree='default' AND level=0 ORDER BY id"
        ).fetchall()
    ]


def test_a_one_topic_tree_is_not_an_orphan(db: Database) -> None:
    # a corpus too small to cluster builds ONE level-0 node, which IS the
    # root. It has no parent because there is nothing above it, and the guard
    # must not read that as an unreachable map.
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 1)

    run(db)  # no exception
    _require_reachable(JobContext(db), "default")  # nor from the guard

    assert _levels(db) == {0: 1}


def test_a_parented_leaf_passes_the_guard(db: Database) -> None:
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 12)

    run(db, lambda n: [i // 3 for i in range(n)])  # 12 -> 4 -> 2 -> 1

    _require_reachable(JobContext(db), "default")  # no exception


def test_build_tree_always_runs_the_reachability_guard(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the guard is only worth having if it is reached. Every shape I can plant
    # is repaired by the collect or the recursion — which is the point of it —
    # so what a test CAN assert is that the pipeline always ends by checking.
    import hrono.summarize.build_tree as module

    checked: list[str] = []
    monkeypatch.setattr(
        module,
        "_require_reachable",
        lambda context, tree: checked.append(tree),
    )
    with db.connect() as conn, conn:
        register(conn)
        seed_leaves(conn, 12)

    run(db, lambda n: [i // 3 for i in range(n)])

    assert checked == ["default"]
