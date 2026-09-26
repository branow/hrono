import json
from collections.abc import Iterator

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import (
    CompletionRequest,
    CompletionResult,
    LLMError,
    Usage,
)
from hrono.registry import store as registry_store
from hrono.summarize import briefs
from hrono.summarize.brief_upper import brief_upper

MODEL = "sonnet"
TEMPLATE = "Abstract across children: {content}"
TREE = "default"


class FakeCompletion:
    def __init__(self, fail_on: int | None = None) -> None:
        self.calls = 0
        self.contents: list[str] = []
        self._fail_on = fail_on

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        self.contents.append(request.content)
        if self._fail_on == self.calls:
            raise LLMError("call failed")
        return CompletionResult(
            "This branch gathers the signing and serialization modules.",
            Usage(50, 20),
        )


def register(conn: object) -> None:
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "models",
        MODEL,
        json.dumps(
            {
                "name": MODEL,
                "kind": "text",
                "connection": "anthropic",
                "model": "claude-sonnet-5",
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
            {"name": "brief-upper", "role": "brief-upper", "template": TEMPLATE}
        ),
        None,
        "t",
    )


def leaf_node(conn: object, label: int, text: str) -> int:
    cursor = conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO nodes(tree, level, label, created_at) "
        "VALUES ('default', 0, ?, 't')",
        (label,),
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
    return node_id


def job(level: int = 1) -> Job:
    return Job(
        id="bu1",
        parent_id=None,
        tree=TREE,
        op="brief-upper",
        scope={"level": level},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def db(tmp_path: object) -> Iterator[tuple[Database, list[int]]]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register(conn)
        a = leaf_node(conn, 0, "child brief A about widgets")
        b = leaf_node(conn, 0, "child brief B about gadgets")
        c = leaf_node(conn, 1, "child brief C about pipelines")
        d = leaf_node(conn, 1, "child brief D about queues")
        # two level-1 parents: {a,b} and {c,d}
        cluster_store.replace_level(
            conn,
            TREE,
            1,
            [
                (0, a, False, None),
                (0, b, False, None),
                (1, c, False, None),
                (1, d, False, None),
            ],
        )
    yield database, [a, b, c, d]
    database.close()


def _parents(db: Database) -> list[int]:
    with db.connect() as conn:
        return [
            int(r["id"])
            for r in conn.execute(
                "SELECT id FROM nodes WHERE level = 1 ORDER BY id"
            ).fetchall()
        ]


def test_brief_upper_is_registered() -> None:
    assert "brief-upper" in OPS


def test_writes_a_parent_brief_from_child_briefs(
    db: Database,
) -> None:
    database, _ = db
    client = FakeCompletion()
    brief_upper(job(), JobContext(database), client=client)
    assert client.calls == 2  # one per level-1 parent
    with database.connect() as conn:
        for parent in _parents(database):
            row = briefs.get(conn, parent)
            assert row is not None
            assert row["model_name"] == MODEL
            assert row["prompt_name"] == "brief-upper"
            assert row["input_tokens"] == 50


def test_input_is_the_child_briefs_not_sections(db: Database) -> None:
    database, _ = db
    client = FakeCompletion()
    brief_upper(job(), JobContext(database), client=client)
    joined = "\n".join(client.contents)
    assert "Abstract across children:" in joined
    assert "child brief A about widgets" in joined
    assert "{content}" not in joined


def test_child_references_are_recorded_beside_the_text(db: Database) -> None:
    # the upper-level twin of the footer problem (#102): the raw "Children:"
    # list used to live in the brief text, where #071 indexed it and render
    # duplicated it as proper titled links.
    database, _ = db
    brief_upper(job(), JobContext(database), client=FakeCompletion())
    parents = _parents(database)
    with database.connect() as conn:
        row = briefs.get(conn, parents[0])
        assert row is not None
        assert "Children:" not in row["text"]
        children = briefs.child_ids(conn, parents[0])
        assert json.loads(row["members"]) == [f"node {c}" for c in children]
        for child in children:
            assert f"node {child}" not in row["text"]


def test_rerun_makes_zero_calls(db: Database) -> None:
    database, _ = db
    brief_upper(job(), JobContext(database), client=FakeCompletion())
    second = FakeCompletion()
    brief_upper(job(), JobContext(database), client=second)
    assert second.calls == 0


def test_failing_parent_keeps_earlier_progress(db: Database) -> None:
    database, _ = db
    with pytest.raises(LLMError):
        brief_upper(
            job(), JobContext(database), client=FakeCompletion(fail_on=2)
        )
    with database.connect() as conn:
        assert (
            conn.execute(
                "SELECT COUNT(*) FROM briefs WHERE node_id IN "
                "(SELECT id FROM nodes WHERE level=1)"
            ).fetchone()[0]
            == 1
        )
    resumed = FakeCompletion()
    brief_upper(job(), JobContext(database), client=resumed)
    assert resumed.calls == 1


def test_the_run_reports_the_tokens_it_spent(db: Database) -> None:
    database, _ = db
    outcome = brief_upper(job(), JobContext(database), client=FakeCompletion())

    assert isinstance(outcome["tokens"], dict)
    assert outcome["tokens"]["input"] > 0  # type: ignore[index]
