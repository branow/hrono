"""T39: settle — churn/misfit trigger + warm reconcile near-no-op."""

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import monitor
from hrono.cluster.build import ClusterResult
from hrono.db.database import Database
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.registry import store as registry_store
from hrono.tree import settle as settle_mod
from hrono.tree.maintain import maintain
from hrono.tree.settle import CHURN_THRESHOLD, settle, should_settle

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
