import hashlib
import json
import time
from collections.abc import Iterator

import pytest

from hrono.cluster import store as cluster_store
from hrono.db.database import Database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.jobs import store as jobs_store
from hrono.jobs.model import Job, serialize_scope
from hrono.jobs.ops import OPS, JobContext
from hrono.jobs.worker import Worker
from hrono.llm.client import (
    CompletionRequest,
    CompletionResult,
    LLMError,
    Usage,
)
from hrono.registry import store as registry_store
from hrono.summarize import briefs
from hrono.summarize import store as condensations
from hrono.summarize.brief import _hash, brief
from hrono.summarize.resolve import resolve_prompt

MODEL = "sonnet"
TEMPLATE = "Brief this group: {content}"
TREE = "default"


class FakeCompletion:
    def __init__(
        self, text: str = "the brief body.", fail_on: int | None = None
    ) -> None:
        self.calls = 0
        self.contents: list[str] = []
        self._text = text
        self._fail_on = fail_on

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        self.contents.append(request.content)
        if self._fail_on == self.calls:
            raise LLMError("call failed")
        return CompletionResult(self._text, Usage(40, 12))


def register_text_model(conn: object) -> None:
    body = {
        "name": MODEL,
        "kind": "text",
        "connection": "anthropic",
        "model": "claude-sonnet-5",
        "params": {},
    }
    registry_store.insert(conn, "models", MODEL, json.dumps(body), None, "t")  # type: ignore[arg-type]


def register_brief_prompt(conn: object) -> None:
    body = {"name": "brief", "role": "brief", "template": TEMPLATE}
    registry_store.insert(conn, "prompts", "brief", json.dumps(body), None, "t")  # type: ignore[arg-type]


def add_condensed_section(conn: object, path: str, body: bytes, i: int) -> int:
    istore.upsert_content(conn, content_hash(body), body)  # type: ignore[arg-type]
    section_id = istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "example.com/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=i,
    )
    condensations.upsert(
        conn,  # type: ignore[arg-type]
        content_hash(body),
        MODEL,
        f"condensation of {path}",
        10,
        3,
    )
    return section_id


def job(scope: dict[str, object] | None = None) -> Job:
    return Job(
        id="b1",
        parent_id=None,
        tree=TREE,
        op="brief",
        scope=scope if scope is not None else {},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_text_model(conn)
        register_brief_prompt(conn)
        s0 = add_condensed_section(conn, "a.py", b"aaa\n", 0)
        s1 = add_condensed_section(conn, "b.py", b"bbb\n", 1)
        s2 = add_condensed_section(conn, "c.py", b"ccc\n", 2)
        s3 = add_condensed_section(conn, "d.py", b"ddd\n", 3)
        # two bottom-level nodes: {s0,s1} and {s2,s3}
        cluster_store.replace_tree(
            conn,
            TREE,
            0,
            [
                (0, s0, False, None),
                (0, s1, False, None),
                (1, s2, False, None),
                (1, s3, False, None),
            ],
            [(s0, [0.1]), (s1, [0.1]), (s2, [0.2]), (s3, [0.2])],
        )
    yield database
    database.close()


def _node_ids(db: Database) -> list[int]:
    with db.connect() as conn:
        return [
            int(r["id"])
            for r in conn.execute("SELECT id FROM nodes ORDER BY id").fetchall()
        ]


def test_brief_is_registered() -> None:
    assert "brief" in OPS


def test_writes_one_brief_per_node_with_provenance(db: Database) -> None:
    client = FakeCompletion()
    brief(job(), JobContext(db), client=client)
    assert client.calls == 2
    with db.connect() as conn:
        for node_id in _node_ids(db):
            row = briefs.get(conn, node_id)
            assert row is not None
            assert row["model_name"] == MODEL
            assert row["prompt_name"] == "brief"
            assert (
                row["prompt_hash"]
                == hashlib.sha256(TEMPLATE.encode()).hexdigest()
            )
            assert row["input_tokens"] == 40
            assert row["output_tokens"] == 12


def test_references_are_appended_mechanically(db: Database) -> None:
    # the fake LLM returns a fixed body with no URIs; every reference in the
    # stored brief therefore came from code, not the model.
    brief(job(), JobContext(db), client=FakeCompletion(text="BODY"))
    nodes = _node_ids(db)
    with db.connect() as conn:
        first = briefs.get(conn, nodes[0])
        assert first is not None
        assert "References:" in first["text"]
        uris = briefs.member_uris(conn, nodes[0])
        assert uris
        for uri in uris:
            assert uri in first["text"]


def test_prompt_is_rendered_over_the_condensations(db: Database) -> None:
    client = FakeCompletion()
    brief(job(), JobContext(db), client=client)
    joined = "\n".join(client.contents)
    assert "Brief this group:" in joined
    assert "condensation of a.py" in joined
    assert "{content}" not in joined


def test_rerun_makes_zero_llm_calls(db: Database) -> None:
    brief(job(), JobContext(db), client=FakeCompletion())
    second = FakeCompletion()
    brief(job(), JobContext(db), client=second)
    assert second.calls == 0


def test_a_failing_node_keeps_earlier_progress_then_rerun_fills_gap(
    db: Database,
) -> None:
    with pytest.raises(LLMError):
        brief(job(), JobContext(db), client=FakeCompletion(fail_on=2))
    with db.connect() as conn:
        stored = conn.execute("SELECT COUNT(*) FROM briefs").fetchone()[0]
    assert stored == 1
    resumed = FakeCompletion()
    brief(job(), JobContext(db), client=resumed)
    assert resumed.calls == 1
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM briefs").fetchone()[0] == 2


def test_node_without_condensations_is_skipped(db: Database) -> None:
    with db.connect() as conn, conn:
        conn.execute("DELETE FROM condensations")
    client = FakeCompletion()
    brief(job(), JobContext(db), client=client)
    assert client.calls == 0
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM briefs").fetchone()[0] == 0


def test_membership_change_marks_the_brief_stale(db: Database) -> None:
    brief(job(), JobContext(db), client=FakeCompletion())
    nodes = _node_ids(db)
    # add a new member section to the first node -> its member signature changes
    with db.connect() as conn, conn:
        new_section = add_condensed_section(conn, "e.py", b"eee\n", 9)
        conn.execute(
            "INSERT INTO node_members(node_id, section_id, attached, "
            "created_at) VALUES (?, ?, 0, 't')",
            (nodes[0], new_section),
        )
    resumed = FakeCompletion()
    brief(job(), JobContext(db), client=resumed)
    assert resumed.calls == 1  # only the node whose membership changed


def test_prompt_template_change_marks_all_briefs_stale(db: Database) -> None:
    brief(job(), JobContext(db), client=FakeCompletion())
    with db.connect() as conn, conn:
        registry_store.replace(
            conn,
            "prompts",
            "brief",
            json.dumps(
                {"name": "brief", "role": "brief", "template": "NEW {content}"}
            ),
            None,
            "t",
        )
    resumed = FakeCompletion()
    brief(job(), JobContext(db), client=resumed)
    assert resumed.calls == 2  # every brief stale under the new prompt hash


def test_unchanged_inputs_keep_briefs_fresh_and_counts_readable(
    db: Database,
) -> None:
    brief(job(), JobContext(db), client=FakeCompletion())
    with db.connect() as conn:
        _, template = resolve_prompt(conn, "brief")
        fresh, stale = briefs.counts(conn, TREE, 0, _hash(template), MODEL)
    assert (fresh, stale) == (2, 0)


def test_membership_change_shows_in_counts(db: Database) -> None:
    brief(job(), JobContext(db), client=FakeCompletion())
    nodes = _node_ids(db)
    with db.connect() as conn, conn:
        new_section = add_condensed_section(conn, "f.py", b"fff\n", 9)
        conn.execute(
            "INSERT INTO node_members(node_id, section_id, attached, "
            "created_at) VALUES (?, ?, 0, 't')",
            (nodes[0], new_section),
        )
    with db.connect() as conn:
        _, template = resolve_prompt(conn, "brief")
        fresh, stale = briefs.counts(conn, TREE, 0, _hash(template), MODEL)
    assert (fresh, stale) == (1, 1)


def test_faithfulness_gate_flags_but_does_not_block(db: Database) -> None:
    # a fabricated identifier in the LLM output is flagged, yet the brief is
    # still stored (flag policy, not hard fail).
    brief(
        job(), JobContext(db), client=FakeCompletion(text="fabricatedToken x")
    )
    with db.connect() as conn:
        rows = conn.execute("SELECT unfaithful FROM briefs").fetchall()
    assert rows  # briefs were stored despite the fabrication
    flagged = [json.loads(r["unfaithful"]) for r in rows]
    assert any("fabricatedToken" in tokens for tokens in flagged)


def test_faithful_brief_records_no_unfaithful_tokens(db: Database) -> None:
    brief(job(), JobContext(db), client=FakeCompletion(text="a plain summary"))
    with db.connect() as conn:
        rows = conn.execute("SELECT unfaithful FROM briefs").fetchall()
    assert rows and all(r["unfaithful"] == "[]" for r in rows)


def test_runs_as_a_job_through_the_worker(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hrono.summarize.brief as brief_mod

    monkeypatch.setattr(
        brief_mod, "_default_client", lambda context: FakeCompletion()
    )
    worker = Worker(db)
    worker.start()
    try:
        with db.connect() as conn:
            jobs_store.insert(
                conn, "bj", None, TREE, "brief", serialize_scope({}), "t"
            )
        deadline = time.monotonic() + 5
        row = None
        while time.monotonic() < deadline:
            with db.connect() as conn:
                row = conn.execute(
                    "SELECT status FROM jobs WHERE id='bj'"
                ).fetchone()
            if row["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.02)
    finally:
        worker.stop()
        worker.join(timeout=5)  # let the claim query finish before we read
    assert row is not None and row["status"] == "succeeded"
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM briefs").fetchone()[0] == 2
