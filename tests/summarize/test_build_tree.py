import json
from collections.abc import Callable, Iterator

import pytest

from hrono.cluster import ClusterError
from hrono.cluster.build import ClusterResult
from hrono.db.database import Database
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.registry import store as registry_store
from hrono.summarize import briefs
from hrono.summarize.build_tree import D_MAX, build_tree

TREE = "default"


class FakeCompletion:
    def complete(self, request: CompletionRequest) -> CompletionResult:
        return CompletionResult("upper brief.", Usage(5, 2))


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
    raise ClusterError("too sparse")


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
    """Every build must end with exactly one node at the top level (#082)."""
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
    # the #082 defect: a multi-top stored tree orphaned sibling top nodes in
    # export. With the collect-root fix, export sees one root and reaches all.
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
    # #094 end to end with the REAL clusterer (no build seam): 7 briefs are
    # below what UMAP can reduce, so cluster-briefs raises ClusterError,
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
