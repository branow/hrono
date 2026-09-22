import json
import time
from collections.abc import Iterator

import pytest

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
from hrono.summarize import store
from hrono.summarize.condense import condense

MODEL = "sonnet"
TEMPLATE = "Condense this: {content}"


class FakeCompletion:
    def __init__(
        self,
        text: str = "a condensation.",
        usage: tuple[int, int] = (12, 4),
        fail_on: int | None = None,
    ) -> None:
        self.calls = 0
        self.contents: list[str] = []
        self._text = text
        self._usage = usage
        self._fail_on = fail_on

    def complete(self, request: CompletionRequest) -> CompletionResult:
        self.calls += 1
        self.contents.append(request.content)
        if self._fail_on == self.calls:
            raise LLMError("call failed")
        return CompletionResult(self._text, Usage(*self._usage))


def register_text_model(conn: object, name: str = MODEL) -> None:
    body = {
        "name": name,
        "kind": "text",
        "connection": "anthropic",
        "model": "claude-sonnet-5",
        "params": {},
    }
    registry_store.insert(conn, "models", name, json.dumps(body), None, "t")  # type: ignore[arg-type]


def register_condense_prompt(conn: object, template: str = TEMPLATE) -> None:
    body = {"name": "condense", "role": "condense", "template": template}
    registry_store.insert(
        conn, "prompts", "condense", json.dumps(body), None, "t"
    )  # type: ignore[arg-type]


def add_section(conn: object, path: str, body: bytes, ordinal: int) -> None:
    istore.upsert_content(conn, content_hash(body), body)  # type: ignore[arg-type]
    istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "example.com/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=ordinal,
    )


def job(scope: dict[str, object] | None = None) -> Job:
    return Job(
        id="c1",
        parent_id=None,
        tree=None,
        op="condense",
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
        register_condense_prompt(conn)
        add_section(conn, "a.py", b"def a(): return 1\n", 0)
        add_section(conn, "b.py", b"def b(): return 2\n", 1)
    yield database
    database.close()


def test_condense_is_registered() -> None:
    assert "condense" in OPS


def test_condenses_each_section_and_records_tokens(db: Database) -> None:
    client = FakeCompletion(text="short.", usage=(30, 7))
    condense(job(), JobContext(db), client=client)
    assert client.calls == 2  # one per distinct section content hash
    with db.connect() as conn:
        assert store.count(conn, MODEL) == 2
        row = store.get(conn, content_hash(b"def a(): return 1\n"), MODEL)
        assert row is not None
        assert row["text"] == "short."
        assert row["input_tokens"] == 30
        assert row["output_tokens"] == 7


def test_rerun_makes_zero_llm_calls(db: Database) -> None:
    condense(job(), JobContext(db), client=FakeCompletion())
    second = FakeCompletion()
    condense(job(), JobContext(db), client=second)
    assert second.calls == 0  # the incremental promise: unchanged -> no calls
    with db.connect() as conn:
        assert store.count(conn, MODEL) == 2


def test_prompt_template_is_rendered_over_the_section_content(
    db: Database,
) -> None:
    client = FakeCompletion()
    condense(job(), JobContext(db), client=client)
    # the seeded template's {content} was replaced with the real section body,
    # and no summarisation vocabulary was hardcoded — it came from the template.
    assert any("Condense this: def a(): return 1" in c for c in client.contents)
    assert all("{content}" not in c for c in client.contents)


def test_content_shared_across_sections_is_condensed_once(db: Database) -> None:
    with db.connect() as conn, conn:
        add_section(conn, "c.py", b"def a(): return 1\n", 2)  # dup body of a.py
    client = FakeCompletion()
    condense(job(), JobContext(db), client=client)
    # three sections but only two distinct content hashes -> two calls
    assert client.calls == 2


def test_a_failing_section_keeps_earlier_progress_then_rerun_fills_gap(
    db: Database,
) -> None:
    failing = FakeCompletion(fail_on=2)
    with pytest.raises(LLMError):
        condense(job(), JobContext(db), client=failing)
    with db.connect() as conn:
        assert (
            store.count(conn, MODEL) == 1
        )  # first section persisted, second not
    resumed = FakeCompletion()
    condense(job(), JobContext(db), client=resumed)
    assert resumed.calls == 1  # only the gap
    with db.connect() as conn:
        assert store.count(conn, MODEL) == 2


def test_no_text_model_raises(db: Database) -> None:
    with db.connect() as conn, conn:
        conn.execute("DELETE FROM registry WHERE collection = 'models'")
    with pytest.raises(LLMError, match="no text model"):
        condense(job(), JobContext(db), client=FakeCompletion())


def test_multiple_text_models_without_a_name_raises(db: Database) -> None:
    with db.connect() as conn, conn:
        register_text_model(conn, "haiku")
    with pytest.raises(LLMError, match="multiple text models"):
        condense(job(), JobContext(db), client=FakeCompletion())


def test_named_model_disambiguates_multiple(db: Database) -> None:
    with db.connect() as conn, conn:
        register_text_model(conn, "haiku")
    client = FakeCompletion()
    condense(
        job({"type": "model", "name": "haiku"}), JobContext(db), client=client
    )
    with db.connect() as conn:
        assert store.count(conn, "haiku") == 2
        assert store.count(conn, MODEL) == 0


def test_no_condense_prompt_raises(db: Database) -> None:
    with db.connect() as conn, conn:
        conn.execute("DELETE FROM registry WHERE collection = 'prompts'")
    with pytest.raises(LLMError, match="no condense prompt"):
        condense(job(), JobContext(db), client=FakeCompletion())


def test_runs_as_a_job_through_the_worker(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hrono.summarize.condense as condense_mod

    monkeypatch.setattr(
        condense_mod, "client_for", lambda context, model: FakeCompletion()
    )
    worker = Worker(db)
    worker.start()
    try:
        with db.connect() as conn:
            jobs_store.insert(
                conn, "cj", None, None, "condense", serialize_scope({}), "t"
            )
        deadline = time.monotonic() + 5
        row = None
        while time.monotonic() < deadline:
            with db.connect() as conn:
                row = conn.execute(
                    "SELECT status FROM jobs WHERE id='cj'"
                ).fetchone()
            if row["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.02)
    finally:
        worker.stop()
        worker.join(timeout=5)  # let the claim query finish before we read
    assert row is not None and row["status"] == "succeeded"
    with db.connect() as conn:
        assert store.count(conn, MODEL) == 2
