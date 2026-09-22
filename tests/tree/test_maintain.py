import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import ClusterError
from hrono.cluster.build import ClusterResult
from hrono.cluster.recipe import MIN_POINTS, recipe_for
from hrono.db.database import Database
from hrono.export import store as export_store
from hrono.export.collapse import collapse
from hrono.export.render import render
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.registry import store as registry_store
from hrono.tree.maintain import maintain
from tests.cluster.invariant import assert_every_leaf_is_reachable
from tests.context import job_context

DIMS = 8


class FakeCompletion:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        return CompletionResult(
            "This topic covers the module's API and how its parts fit.",
            Usage(10, 4),
        )


def fake_encoder(model_id: str):
    def encode(texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (DIMS - 1) for _ in texts]

    return encode


def fake_build(vectors: object, *, init: object = None) -> ClusterResult:
    n = len(vectors)  # type: ignore[arg-type]
    labels = [i // 3 for i in range(n)]  # reduces ~3:1 per level -> root
    return ClusterResult(
        labels=tuple(labels),
        attached=tuple(False for _ in range(n)),
        assignment_similarity=tuple(None for _ in range(n)),
        coords=tuple((0.0,) for _ in range(n)),
    )


def make_repo(path: Path, files: int = 9) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "t@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"], check=True
    )
    for i in range(files):
        (path / f"f{i}.txt").write_text(f"module {i} does thing number {i}\n")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(
        ["git", "-C", str(path), "commit", "-qm", "first"], check=True
    )
    return path.as_uri()


def register(conn: object, url: str) -> None:
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "sources",
        "repo",
        json.dumps({"name": "repo", "type": "git", "url": url, "auth": {}}),
        None,
        "t",
    )
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
                "params": {"dims": DIMS, "batch_size": 8},
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
    for role in ("condense", "brief", "brief-upper"):
        registry_store.insert(
            conn,  # type: ignore[arg-type]
            "prompts",
            role,
            json.dumps({"name": role, "role": role, "template": "X {content}"}),
            None,
            "t",
        )


def job() -> Job:
    return Job(
        id="m1",
        parent_id=None,
        tree="default",
        op="maintain",
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


def run(db: Database, tmp_path: Path) -> None:
    maintain(
        job(),
        job_context(db, tmp_path),
        encoder_for=fake_encoder,
        client=FakeCompletion(),
        build=fake_build,
    )


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Database]:
    monkeypatch.chdir(tmp_path)
    url = make_repo(tmp_path / "src-repo")
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register(conn, url)
    yield database
    database.close()


def _count(db: Database, table: str) -> int:
    with db.connect() as conn:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def test_maintain_is_registered() -> None:
    assert "maintain" in OPS


def test_builds_a_fresh_tree_end_to_end_to_a_single_root(
    db: Database, tmp_path: Path
) -> None:
    run(db, tmp_path)
    assert _count(db, "sections") >= 3  # sync + split ran
    assert _count(db, "embeddings") > 0  # embed ran
    assert _count(db, "condensations") >= 3  # condense ran
    assert _count(db, "briefs") > 0  # cluster + brief ran
    with db.connect() as conn:
        levels = conn.execute(
            "SELECT level, COUNT(*) c FROM nodes GROUP BY level"
        ).fetchall()
    by_level = {int(r["level"]): int(r["c"]) for r in levels}
    assert max(by_level) >= 1  # recursed above the leaf level
    assert by_level[max(by_level)] == 1  # to a single root
    assert_every_leaf_is_reachable(db, "default")  # every topic on the map


def _source_embeddings(db: Database) -> int:
    with db.connect() as conn:
        return int(
            conn.execute(
                "SELECT COUNT(*) FROM embeddings e WHERE EXISTS ("
                "SELECT 1 FROM sections s WHERE "
                "s.content_hash = e.content_hash "
                "AND s.source_type != 'node')"
            ).fetchone()[0]
        )


def test_second_maintain_re_condenses_and_re_embeds_source_nothing(
    db: Database,
    tmp_path: Path,
) -> None:
    run(db, tmp_path)
    condensations = _count(db, "condensations")
    source_embeddings = _source_embeddings(db)
    run(db, tmp_path)  # unchanged tree
    # the M4 content-hash caches hold: condense (the expensive LLM map) does
    # zero new work, and no source section is re-embedded.
    assert _count(db, "condensations") == condensations
    assert _source_embeddings(db) == source_embeddings
    # briefs no longer churn either now that #068 keeps node ids stable — the
    # stronger zero-LLM-calls proof is the test below.


def _node_ids(db: Database) -> list[int]:
    with db.connect() as conn:
        return sorted(
            int(r["id"])
            for r in conn.execute("SELECT id FROM nodes").fetchall()
        )


def test_second_maintain_makes_zero_llm_calls_and_keeps_node_ids(
    db: Database,
    tmp_path: Path,
) -> None:
    # the incremental differentiator, now whole (#068): once built, a second
    # maintain over an unchanged corpus regenerates NO briefs — cluster reuses
    # node ids by content signature so briefs survive #064's skip.
    first = FakeCompletion()
    maintain(
        job(),
        job_context(db, tmp_path),
        encoder_for=fake_encoder,
        client=first,
        build=fake_build,
    )
    assert first.calls > 0  # a real build happened
    ids_before = _node_ids(db)

    second = FakeCompletion()
    maintain(
        job(),
        job_context(db, tmp_path),
        encoder_for=fake_encoder,
        client=second,
        build=fake_build,
    )
    assert second.calls == 0  # condense + brief + brief-upper all skip
    assert _node_ids(db) == ids_before  # stable node identity across rebuilds


def test_missing_embedding_model_fails_the_maintain_run(
    db: Database, tmp_path: Path
) -> None:
    with db.connect() as conn, conn:
        conn.execute("DELETE FROM registry WHERE name = 'emb'")
    with pytest.raises(Exception):  # noqa: B017 - any clean stage error aborts
        run(db, tmp_path)


def _tiny_db(tmp_path: Path) -> Database:
    """A corpus of three files — far below the smallest clustering rung."""
    url = make_repo(tmp_path / "tiny-repo", files=3)
    database = Database.at(tmp_path / "tiny.db")
    with database.connect() as conn, conn:
        register(conn, url)
    return database


def test_a_corpus_below_the_smallest_rung_builds_one_topic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # #112: the REAL clustering backend over a sub-MIN_POINTS corpus. The ladder
    # (#094) cannot reduce it, and "cannot reduce" must mean "then this IS the
    # topic" — the move `_collect_root` already makes at the top of the tree —
    # not a failed job and a user with no tree.
    monkeypatch.chdir(tmp_path)
    database = _tiny_db(tmp_path)
    try:
        maintain(  # no `build=`: the real recipe, which raises below the rung
            job(),
            job_context(database, tmp_path),
            encoder_for=fake_encoder,
            client=FakeCompletion(),
        )
        assert _count(database, "sections") < MIN_POINTS
        with database.connect() as conn:
            levels = conn.execute(
                "SELECT level, COUNT(*) c FROM nodes GROUP BY level"
            ).fetchall()
            root = conn.execute(
                "SELECT b.text AS t FROM briefs b JOIN nodes n "
                "ON n.id = b.node_id WHERE n.level = ("
                "SELECT MAX(level) FROM nodes)"
            ).fetchone()
        by_level = {int(r["level"]): int(r["c"]) for r in levels}
        assert by_level == {0: 1}  # one topic, which is also the root
        assert root["t"]  # briefed, with content
        with database.connect() as conn:
            how = conn.execute(
                "SELECT DISTINCT attached, assignment_similarity AS sim "
                "FROM node_members"
            ).fetchall()
        # nothing was attached by proximity because nothing clustered: the flag
        # is a claim about HOW a member arrived, and #114/#124 read it.
        assert [(int(r["attached"]), r["sim"]) for r in how] == [(0, None)]
        assert_every_leaf_is_reachable(database, "default")

        with database.connect() as conn:
            stored = export_store.load(conn, "default")
            assert stored is not None
            exported = render(conn, collapse(stored, 3))
        assert "root.md" in exported
        assert exported["root.md"].strip()
    finally:
        database.close()


def test_the_recipe_ladder_still_refuses_below_its_floor() -> None:
    # the collect is the CALLER's decision, not a new rung: `build_tree` reads
    # this same ClusterError as "the current top is the root" (#094).
    with pytest.raises(ClusterError):
        recipe_for(MIN_POINTS - 1)


def test_a_broken_backend_fails_the_job_it_does_not_collect(
    db: Database, tmp_path: Path
) -> None:
    # #112's collect is decided by the point count, never by catching the
    # backend's error: `build_clusters` raises the same `ClusterError` when the
    # reduction fails, when the clusterer fails, when it produces no clusters
    # and when it is not installed. Collapsing a corpus into one topic because
    # its clustering BROKE would answer with a confident, wrong map.
    def broken(vectors: object, *, init: object = None) -> ClusterResult:
        raise ClusterError("the reduction failed on these vectors")

    with pytest.raises(ClusterError):
        maintain(
            job(),
            job_context(db, tmp_path),
            encoder_for=fake_encoder,
            client=FakeCompletion(),
            build=broken,
        )
    assert _count(db, "nodes") == 0  # nothing invented on the way out
