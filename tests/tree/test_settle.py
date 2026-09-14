"""T39: settle — churn/misfit trigger + warm reconcile near-no-op."""

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import monitor
from hrono.cluster.blend import register_path_bodies
from hrono.cluster.build import ClusterResult
from hrono.cluster.incubator import count as incubator_count
from hrono.cluster.incubator import park
from hrono.cluster.recipe import MIN_POINTS
from hrono.db.database import Database
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.registry import store as registry_store
from hrono.summarize import store as condensations
from hrono.tree import settle as settle_mod
from hrono.tree.maintain import maintain
from hrono.tree.settle import CHURN_THRESHOLD, settle, should_settle
from tests.cluster.harness import planted_groups
from tests.cluster.invariant import assert_pool_invariant

DIMS = 8
TREE = "default"


class FakeCompletion:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        return CompletionResult("a plain summary.", Usage(10, 4))


def fake_encoder(model_id: str):
    def encode(texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (DIMS - 1) for _ in texts]

    return encode


def fake_build(vectors: object, *, init: object = None) -> ClusterResult:
    n = len(vectors)  # type: ignore[arg-type]
    return ClusterResult(
        labels=tuple(i // 3 for i in range(n)),
        attached=tuple(False for _ in range(n)),
        assignment_similarity=tuple(None for _ in range(n)),
        coords=tuple((0.0,) for _ in range(n)),
    )


def make_repo(path: Path) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    subprocess.run(
        ["git", "-C", str(path), "config", "user.email", "t@example.com"],
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(path), "config", "user.name", "Test"], check=True
    )
    for i in range(9):
        (path / f"f{i}.txt").write_text(f"module {i} does thing {i}\n")
    subprocess.run(["git", "-C", str(path), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(path), "commit", "-qm", "one"], check=True)
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


def _job() -> Job:
    return Job(
        id="s",
        parent_id=None,
        tree=TREE,
        op="settle",
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Database]:
    monkeypatch.chdir(tmp_path)
    url = make_repo(tmp_path / "src-repo")
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register(conn, url)
    maintain(
        Job(
            id="m",
            parent_id=None,
            tree=TREE,
            op="maintain",
            scope={},
            status="running",
            error=None,
            created_at="t",
            updated_at="t",
        ),
        JobContext(database),
        encoder_for=fake_encoder,
        client=FakeCompletion(),
        build=fake_build,
    )
    yield database
    database.close()


def _set_drift(db: Database, drift: int) -> None:
    with db.connect() as conn, conn:
        conn.execute(
            "INSERT INTO tree_batch(tree, batch, drift) VALUES (?, 0, ?) "
            "ON CONFLICT(tree) DO UPDATE SET drift = excluded.drift",
            (TREE, drift),
        )


def _drift(db: Database) -> int:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT drift FROM tree_batch WHERE tree = ?", (TREE,)
        ).fetchone()
        return int(row["drift"]) if row else 0


def _node_ids(db: Database) -> list[int]:
    with db.connect() as conn:
        return sorted(
            int(r["id"]) for r in conn.execute("SELECT id FROM nodes")
        )


def test_registered() -> None:
    assert "settle" in OPS


def test_churn_threshold_triggers(built: Database) -> None:
    with built.connect() as conn:
        assert should_settle(conn, TREE) is False  # fresh, no drift
    _set_drift(built, CHURN_THRESHOLD)
    with built.connect() as conn:
        assert should_settle(conn, TREE) is True


def test_misfit_backstop_triggers(built: Database) -> None:
    with built.connect() as conn, conn:
        # baseline low, current global misfit high -> backstop trips
        monitor.capture_baseline(conn, TREE, 0.01)
        conn.execute(
            "INSERT INTO misfit(tree, node_id, misfits, members, updated_at) "
            "SELECT ?, id, 1, 1, 't' FROM nodes WHERE tree = ? AND level = 0",
            (TREE, TREE),
        )
    with built.connect() as conn:
        assert monitor.global_rate(conn, TREE) > 2 * 0.01
        assert should_settle(conn, TREE) is True


def test_settle_over_unchanged_corpus_is_near_no_op(built: Database) -> None:
    ids_before = _node_ids(built)
    counter = FakeCompletion()
    settle(
        _job(),
        JobContext(built),
        force=True,
        build=fake_build,
        encoder_for=fake_encoder,
        client=counter,
    )
    # warm rebuild reproduces the layout: #068 keeps ids, #064 skips every brief
    assert counter.calls == 0
    assert _node_ids(built) == ids_before


def test_settle_resets_the_churn_counter(built: Database) -> None:
    _set_drift(built, CHURN_THRESHOLD + 5)
    settle(
        _job(),
        JobContext(built),
        build=fake_build,
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )
    assert _drift(built) == 0


def test_untriggered_settle_leaves_the_counter(built: Database) -> None:
    _set_drift(built, 3)  # below threshold, no misfit backstop
    settle_mod.settle(
        _job(),
        JobContext(built),
        build=fake_build,
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )
    assert _drift(built) == 3  # never ran, counter untouched


def _park_a_member(db: Database) -> int:
    """Park a chunk that a rebuild will home — the #095 'both' violation."""
    with db.connect() as conn, conn:
        row = conn.execute(
            "SELECT section_id FROM node_members LIMIT 1"
        ).fetchone()
        park(conn, TREE, int(row["section_id"]), batch=1)
    return int(row["section_id"])


def test_settle_retires_a_pool_row_its_rebuild_has_re_homed(
    built: Database,
) -> None:
    section_id = _park_a_member(built)
    with built.connect() as conn:
        assert incubator_count(conn, TREE) == 1
    settle(
        _job(),
        JobContext(built),
        force=True,
        build=fake_build,
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )
    with built.connect() as conn:
        assert incubator_count(conn, TREE) == 0, section_id
    assert_pool_invariant(built, TREE, "emb")


def _park_unembedded(db: Database, count: int) -> None:
    """Park chunks the rebuild cannot see — they embed only later in settle."""
    path = "late/arrivals.txt"
    with db.connect() as conn, conn:
        register_path_bodies(conn, [path])
        for i in range(count):
            body = f"late arrival {i}\n".encode()
            digest = content_hash(body)
            upsert_content(conn, digest, body)
            section_id = insert_section(
                conn,
                source="repo",
                address=Address("git", "ex/repo", path, "v1"),
                start=0,
                end=len(body),
                content_hash=digest,
                ordinal=0,
            )
            park(conn, TREE, section_id, batch=1)
            condensations.upsert(conn, digest, "sonnet", "a plain gist.", 1, 1)


def test_settle_drains_chunks_its_own_embed_pass_made_placeable(
    built: Database,
) -> None:
    # cluster runs before embed, so a chunk with no vector yet is invisible to
    # the rebuild; settle's closing drain is what re-homes it.
    _park_unembedded(built, MIN_POINTS)
    settle(
        _job(),
        JobContext(built),
        force=True,
        build=fake_build,
        encoder_for=fake_encoder,
        client=FakeCompletion(),
    )
    with built.connect() as conn:
        assert incubator_count(conn, TREE) == 0
    assert_pool_invariant(built, TREE, "emb")


def _leaf_ids(db: Database) -> list[int]:
    with db.connect() as conn:
        return [
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM nodes WHERE tree = ? AND level = 0", (TREE,)
            ).fetchall()
        ]


def _briefed(db: Database) -> set[int]:
    with db.connect() as conn:
        return {
            int(row["node_id"])
            for row in conn.execute("SELECT node_id FROM briefs").fetchall()
        }


def planted_encoder(model_id: str):
    """Give the parked late arrivals their own density core, everything else
    the flat corpus direction."""
    vectors, _ = planted_groups(
        groups=2, per_group=7, dim=DIMS - 1, spread=0.1, noise=0, seed=1
    )

    def encode(texts: list[str]) -> list[list[float]]:
        out = []
        for text in texts:
            if text.startswith("late arrival "):
                index = int(text.split()[2])
                out.append([0.0] + [float(v) for v in vectors[index]])
            else:
                out.append([1.0] + [0.0] * (DIMS - 1))
        return out

    return encode


def test_a_leaf_node_the_settle_drain_emits_is_briefed(
    built: Database,
) -> None:
    # the drain runs BEFORE the brief pass, so a leaf node it emits is
    # summarised in the same settle rather than left blank until the next
    # trigger — with drift already reset, nothing would re-trigger.
    before = _leaf_ids(built)
    _park_unembedded(built, 14)
    settle(
        _job(),
        JobContext(built),
        force=True,
        build=fake_build,
        encoder_for=planted_encoder,
        client=FakeCompletion(),
    )
    emitted = set(_leaf_ids(built)) - set(before)
    assert emitted  # the drain reduced the pool into real clusters
    assert emitted <= _briefed(built)
    assert_pool_invariant(built, TREE, "emb")
