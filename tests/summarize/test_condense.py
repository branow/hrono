import json
import threading
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
from hrono.summarize import pool, store
from hrono.summarize.condense import condense
from tests.summarize.concurrent_client import Overlap, Paired

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


class Reclaiming:
    """Takes its own job out of ``running`` the way a lost worker's does.

    ``store.reclaim`` is what the worker's heartbeat sweep calls on a job whose
    holder stopped stamping it (#111) — a production writer, so this test does
    not construct the state it then asserts on. It is also the shape a stop
    takes: the op's guard is "my row no longer says running", whoever wrote it.
    """

    def __init__(self, database: Database) -> None:
        self._database = database
        self.calls = 0
        self._guard = threading.Lock()

    def complete(self, request: CompletionRequest) -> CompletionResult:
        with self._guard:
            self.calls += 1
            first = self.calls == 1
        if first:
            with self._database.connect() as conn:
                jobs_store.reclaim(conn, None, "t")
        return CompletionResult("a condensation.", Usage(1, 1))


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


def test_the_run_reports_what_it_condensed_and_spent(db: Database) -> None:
    # condense returned NO outcome at all until #179 -- the most expensive
    # stage of a first build was the one nobody could account for.
    outcome = condense(job(), JobContext(db), client=FakeCompletion())

    assert outcome["condensed"] > 0
    assert isinstance(outcome["tokens"], dict)
    assert outcome["tokens"]["input"] > 0  # type: ignore[index]


def test_calls_overlap_so_a_first_build_is_not_serial(db: Database) -> None:
    # 421 sections at 4-30 s each was 70 minutes of an idle process. A results
    # assertion passes against the serial loop, so this one asserts the
    # OVERLAP: `Paired` answers only in twos and times out if it is alone.
    with db.connect() as conn, conn:
        add_section(conn, "c.py", b"def c(): return 3\n", 2)
        add_section(conn, "d.py", b"def d(): return 4\n", 3)
    client = Paired()

    outcome = condense(job(), JobContext(db), client=client)

    assert client.peak >= 2
    assert outcome["condensed"] == 4
    with db.connect() as conn:
        assert store.count(conn, MODEL) == 4


def test_the_env_var_holds_the_pool_to_one_call_at_a_time(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the knob an operator reaches for on a rate limit or a small box. `peak`
    # cannot read 1 unless the calls really were serialised.
    monkeypatch.setenv(pool.ENV_WIDTH, "1")
    client = Overlap()

    condense(job(), JobContext(db), client=client)

    assert client.calls == 2
    assert client.peak == 1


def test_a_job_that_leaves_running_stops_launching_calls(db: Database) -> None:
    """A stop must not have to wait out every remaining section."""
    with db.connect() as conn, conn:
        for i, name in enumerate("efghijkl"):
            add_section(
                conn, f"{name}.py", f"def {name}(): pass\n".encode(), i + 2
            )
        jobs_store.insert(
            conn, "c1", None, None, "condense", serialize_scope({}), "t"
        )
        assert jobs_store.claim_next(conn, "t") is not None  # -> running

    client = Reclaiming(db)
    outcome = condense(job(), JobContext(db), client=client)

    assert 0 < client.calls < 10  # ten pending sections; the pool stopped
    with db.connect() as conn:
        assert store.count(conn, MODEL) == client.calls  # all of it kept
    assert outcome["condensed"] == client.calls
