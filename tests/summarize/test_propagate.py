"""T36: the propagate judge cascade — mark ancestors stale, marks only."""

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster import store as cluster_store
from hrono.cluster.build import ClusterResult
from hrono.db.database import Database, open_database
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import (
    Completion,
    CompletionRequest,
    CompletionResult,
    Usage,
)
from hrono.registry import store as registry_store
from hrono.summarize import briefs, propagate
from hrono.summarize.propagate import _majority, _verdict

TREE = "default"


class FakeJudge:
    def __init__(self, word: str) -> None:
        self.word = word
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        return CompletionResult(self.word, Usage(1, 1))


def _register(conn: object) -> None:
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
        "judge",
        json.dumps(
            {
                "name": "judge",
                "role": "judge",
                "template": "S {source} M {summary}",
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


def _brief(conn: object, node_id: int, member_sig: str) -> None:
    briefs.upsert(
        conn,  # type: ignore[arg-type]
        node_id,
        f"brief for {node_id}",
        model_name="sonnet",
        prompt_name="brief-upper",
        prompt_hash="h",
        member_signature=member_sig,
        input_tokens=1,
        output_tokens=1,
    )


def _leaf(conn: object) -> int:
    """A level-0 node whose stored brief signature no longer matches."""
    members = []
    for i in range(2):
        body = f"leaf section {i}\n".encode()
        digest = content_hash(body)
        upsert_content(conn, digest, body)  # type: ignore[arg-type]
        members.append(
            insert_section(
                conn,  # type: ignore[arg-type]
                source="repo",
                address=Address("git", "ex/repo", "f.txt", "v1"),
                start=0,
                end=len(body),
                content_hash=digest,
                ordinal=i,
            )
        )
    node_id = cluster_store.add_leaf_node(
        conn, TREE, [(s, False, None) for s in members]
    )
    _brief(conn, node_id, member_sig="STALE-DOES-NOT-MATCH")
    return node_id


def _upper(conn: object, level: int, child_id: int) -> int:
    cursor = conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO nodes(tree, level, label, created_at) VALUES (?, ?, 0, ?)",
        (TREE, level, "t"),
    )
    node_id = int(cursor.lastrowid or 0)
    conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO node_children(parent_id, child_id, attached, "
        "assignment_similarity, created_at) VALUES (?, ?, 0, NULL, ?)",
        (node_id, child_id, "t"),
    )
    _brief(conn, node_id, member_sig=f"sig-{level}")
    return node_id


def _job() -> Job:
    return Job(
        id="p",
        parent_id=None,
        tree=TREE,
        op="propagate",
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database(open_database(tmp_path / "hrono.db"))
    with database.connect() as conn, conn:
        _register(conn)
    yield database
    database.close()


def _run(db: Database, judge: Completion) -> None:
    propagate.propagate(_job(), JobContext(db), client=judge)


def _stale(db: Database, node_id: int) -> int:
    with db.connect() as conn:
        return int(briefs.get(conn, node_id)["stale"])


def test_registered() -> None:
    assert "propagate" in OPS


def test_majority_of_three() -> None:
    assert _majority(["none", "none", "major"]) == "none"
    assert _majority(["minor", "major", "major"]) == "major"
    assert _majority(["none", "minor", "major"]) == "minor"


def test_verdict_parsing() -> None:
    assert _verdict("This is a MAJOR change") == "major"
    assert _verdict("only a minor tweak") == "minor"
    assert _verdict("no meaningful change") == "none"


def test_material_verdict_climbs_ancestors_bounded_by_d_max(
    db: Database,
) -> None:
    with db.connect() as conn, conn:
        leaf = _leaf(conn)
        ancestors = []
        child = leaf
        for level in range(1, 7):  # six ancestors: n1..n6
            child = _upper(conn, level, child)
            ancestors.append(child)

    judge = FakeJudge("major")
    _run(db, judge)

    assert judge.calls == 3  # best-of-3 over the one changed leaf
    # D_MAX is 5: the nearest five ancestors are marked, the sixth is not
    assert [_stale(db, n) for n in ancestors] == [1, 1, 1, 1, 1, 0]
    with db.connect() as conn:
        log = conn.execute(
            "SELECT verdict, action, climbed_to FROM update_log"
        ).fetchall()
        drift = conn.execute(
            "SELECT drift FROM tree_batch WHERE tree = ?", (TREE,)
        ).fetchone()["drift"]
    assert len(log) == 1
    assert log[0]["verdict"] == "major" and log[0]["action"] == "propagated"
    assert log[0]["climbed_to"] == 5  # highest level marked
    assert drift == 2  # major contributes 2


def test_none_verdict_marks_nothing_and_logs_skip(db: Database) -> None:
    with db.connect() as conn, conn:
        leaf = _leaf(conn)
        parent = _upper(conn, 1, leaf)

    _run(db, FakeJudge("none"))

    assert _stale(db, parent) == 0  # climb never started
    with db.connect() as conn:
        row = conn.execute(
            "SELECT verdict, action, climbed_to FROM update_log"
        ).fetchone()
    assert row["action"] == "skipped" and row["climbed_to"] is None


def test_unchanged_leaf_is_not_judged(db: Database) -> None:
    with db.connect() as conn, conn:
        # a leaf whose stored brief signature matches its members: not changed
        members = []
        body = b"stable\n"
        digest = content_hash(body)
        upsert_content(conn, digest, body)
        members.append(
            insert_section(
                conn,
                source="repo",
                address=Address("git", "ex/repo", "s.txt", "v1"),
                start=0,
                end=len(body),
                content_hash=digest,
                ordinal=0,
            )
        )
        node_id = cluster_store.add_leaf_node(
            conn, TREE, [(members[0], False, None)]
        )
        _brief(conn, node_id, member_sig=briefs.member_signature(conn, node_id))

    judge = FakeJudge("major")
    _run(db, judge)
    assert judge.calls == 0  # nothing changed, nothing judged


DIMS = 8


class FakeCompletion:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        return CompletionResult("a plain summary.", Usage(10, 4))


def _fake_encoder(model_id: str):
    def encode(texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * (DIMS - 1) for _ in texts]

    return encode


def _fake_build(vectors: object, *, init: object = None) -> ClusterResult:
    n = len(vectors)  # type: ignore[arg-type]
    return ClusterResult(
        labels=tuple(i // 3 for i in range(n)),
        attached=tuple(False for _ in range(n)),
        assignment_similarity=tuple(None for _ in range(n)),
        coords=tuple((0.0,) for _ in range(n)),
    )


def _make_repo(path: Path) -> str:
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


def test_marked_ancestor_regenerates_only_the_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    url = _make_repo(tmp_path / "src-repo")
    database = Database(open_database(tmp_path / "hrono.db"))
    try:
        with database.connect() as conn, conn:
            registry_store.insert(
                conn,
                "sources",
                "repo",
                json.dumps(
                    {"name": "repo", "type": "git", "url": url, "auth": {}}
                ),
                None,
                "t",
            )
            registry_store.insert(
                conn,
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
            _register(conn)
        from hrono.tree.maintain import maintain

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
            encoder_for=_fake_encoder,
            client=FakeCompletion(),
            build=_fake_build,
        )

        # simulate an update that changed one leaf's membership
        with database.connect() as conn, conn:
            leaf = int(
                conn.execute(
                    "SELECT id FROM nodes WHERE tree = ? AND level = 0 "
                    "ORDER BY id LIMIT 1",
                    (TREE,),
                ).fetchone()["id"]
            )
            members = cluster_store.node_member_rows(conn, leaf)
            cluster_store.remove_member(conn, leaf, members[0][0])

        # before propagate: the parent looks fresh (#068 signature unchanged)
        from hrono.summarize.brief_upper import brief_upper

        before = FakeCompletion()
        brief_upper(
            Job(
                id="bu",
                parent_id=None,
                tree=TREE,
                op="brief-upper",
                scope={"level": 1},
                status="running",
                error=None,
                created_at="t",
                updated_at="t",
            ),
            JobContext(database),
            client=before,
        )
        assert before.calls == 0  # nothing regenerates without propagate

        propagate.propagate(
            _job(), JobContext(database), client=FakeJudge("major")
        )

        after = FakeCompletion()
        brief_upper(
            Job(
                id="bu2",
                parent_id=None,
                tree=TREE,
                op="brief-upper",
                scope={"level": 1},
                status="running",
                error=None,
                created_at="t",
                updated_at="t",
            ),
            JobContext(database),
            client=after,
        )
        assert after.calls >= 1  # only the marked ancestor path regenerates
    finally:
        database.close()
