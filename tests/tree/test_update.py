"""T34 op: `update` applies a change batch incrementally over a built tree."""

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster.build import ClusterResult
from hrono.db.database import Database
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import CompletionRequest, CompletionResult, Usage
from hrono.registry import store as registry_store
from hrono.tree.maintain import maintain
from hrono.tree.update import update

DIMS = 8


class FakeCompletion:
    def complete(self, request: CompletionRequest) -> CompletionResult:
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


def _git(path: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(path), *args], check=True)


def make_repo(path: Path, files: int = 9) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "Test")
    for i in range(files):
        (path / f"f{i}.txt").write_text(f"module {i} does thing number {i}\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "first")
    return path.as_uri()


def edit(path: Path, name: str, text: str) -> None:
    (path / name).write_text(text)
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", f"edit {name}")


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


def _job(op: str) -> Job:
    return Job(
        id=op,
        parent_id=None,
        tree="default",
        op=op,
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[Database, Path]]:
    monkeypatch.chdir(tmp_path)
    origin = tmp_path / "src-repo"
    url = make_repo(origin)
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register(conn, url)
    maintain(
        _job("maintain"),
        JobContext(database),
        encoder_for=fake_encoder,
        client=FakeCompletion(),
        build=fake_build,
    )
    yield database, origin
    database.close()


def _section_ids(db: Database, path: str) -> list[int]:
    with db.connect() as conn:
        return sorted(
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM sections WHERE path = ?", (path,)
            ).fetchall()
        )


def _hashes(db: Database, path: str) -> set[str]:
    with db.connect() as conn:
        return {
            r["content_hash"]
            for r in conn.execute(
                "SELECT content_hash FROM sections WHERE path = ?", (path,)
            ).fetchall()
        }


def _node_ids(db: Database) -> list[int]:
    with db.connect() as conn:
        return sorted(
            int(r["id"]) for r in conn.execute("SELECT id FROM nodes")
        )


def test_update_is_registered() -> None:
    assert "update" in OPS


def test_update_swaps_changed_file_and_leaves_untouched_alone(
    built: tuple[Database, Path],
) -> None:
    db, origin = built
    before_f1 = _section_ids(db, "f1.txt")  # untouched file
    old_f0 = _hashes(db, "f0.txt")

    edit(origin, "f0.txt", "module 0 has been completely rewritten now\n")
    update(_job("update"), JobContext(db), encoder_for=fake_encoder)

    assert _hashes(db, "f0.txt") and _hashes(db, "f0.txt") != old_f0
    assert _section_ids(db, "f1.txt") == before_f1  # never touched
    assert _node_ids(db)  # tree intact, not destroyed


def test_update_with_no_change_is_a_noop(built: tuple[Database, Path]) -> None:
    db, _origin = built
    nodes_before = _node_ids(db)
    with db.connect() as conn:
        sections_before = int(
            conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        )

    update(_job("update"), JobContext(db), encoder_for=fake_encoder)

    with db.connect() as conn:
        sections_after = int(
            conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]
        )
    assert sections_after == sections_before
    assert _node_ids(db) == nodes_before
