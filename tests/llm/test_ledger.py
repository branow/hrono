"""Every model call writes one ledger row, whatever became of it."""

import ast
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.embed.encoders import encoder_for_model
from hrono.jobs.ops import JobContext
from hrono.jobs.scope import fan_out
from hrono.jobs.worker import enqueue
from hrono.llm import claude_code, client, openai, providers
from hrono.llm.client import (
    CompletionRequest,
    CompletionResult,
    LLMError,
    Usage,
)
from hrono.llm.ledger import Ledgered
from hrono.registry import store as registry_store
from hrono.server.app import create_app
from hrono.summarize import packed, pool
from hrono.summarize.condense import condense
from tests.context import job_context
from tests.summarize.concurrent_client import Overlap
from tests.summarize.test_condense import (
    add_section,
    job,
    register_condense_prompt,
    register_text_model,
)

SRC = Path(__file__).resolve().parents[2] / "src" / "hrono"
MODEL = {"name": "writer", "kind": "text", "model": "claude-sonnet-5"}


class Ticking:
    """A clock that advances a fixed step each time it is read."""

    def __init__(self, step: float) -> None:
        self._now = 0.0
        self._step = step

    def __call__(self) -> float:
        self._now += self._step
        return self._now


class Answering:
    def __init__(self, usage: Usage) -> None:
        self._usage = usage

    def complete(self, request: CompletionRequest) -> CompletionResult:
        return CompletionResult("a brief.", self._usage)


class Failing:
    def complete(self, request: CompletionRequest) -> CompletionResult:
        raise LLMError("upstream said no")


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    yield database
    database.close()


def _calls(database: Database) -> list[dict[str, object]]:
    with database.connect() as conn:
        rows = conn.execute("SELECT * FROM llm_calls ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def _request() -> CompletionRequest:
    return CompletionRequest(model=MODEL, system="", content="text")


def test_a_call_is_recorded_with_what_it_spent(db: Database) -> None:
    usage = Usage(9, 43, cache_read=7, cache_creation=14563, model="up-1")
    ledgered = Ledgered(
        Answering(usage),
        JobContext(db, job_id="job_a"),
        role="brief",
        provider="claude-code",
        clock=Ticking(0.25),
    )

    ledgered.complete(_request())

    [row] = _calls(db)
    assert {k: row[k] for k in row if k not in ("id", "created_at")} == {
        "job_id": "job_a",
        "run_id": "job_a",  # no jobs row: the job is its own run
        "started_by": None,
        "model": "writer",
        "role": "brief",
        "provider": "claude-code",
        "upstream_model": "up-1",
        "input_tokens": 9,
        "output_tokens": 43,
        "cache_read_tokens": 7,
        "cache_creation_tokens": 14563,
        "duration_ms": 250,
        "ok": 1,
    }


def test_a_failed_call_is_recorded_and_still_raises(db: Database) -> None:
    ledgered = Ledgered(
        Failing(), JobContext(db), role="judge", provider="anthropic"
    )

    with pytest.raises(LLMError, match="upstream said no"):
        ledgered.complete(_request())

    [row] = _calls(db)
    assert (row["ok"], row["role"], row["input_tokens"]) == (0, "judge", None)


def test_a_retried_call_is_two_rows(db: Database) -> None:
    ledgered = Ledgered(
        Answering(Usage(1, 1)), JobContext(db), role="b", provider="p"
    )

    ledgered.complete(_request())
    ledgered.complete(_request())

    assert len(_calls(db)) == 2


def test_a_fan_out_leaf_books_its_calls_to_the_run_and_its_starter(
    db: Database,
) -> None:
    with db.write() as conn:
        for name in ("a", "b"):
            registry_store.insert(
                conn, "sources", name, json.dumps({"name": name}), None, "t"
            )
    parent = fan_out(
        db, "sync", {"type": "all"}, tree="default", started_by="ana"
    )
    with db.connect() as conn:
        leaf = conn.execute(
            "SELECT id, started_by FROM jobs WHERE parent_id = ? LIMIT 1",
            (parent,),
        ).fetchone()
    ledgered = Ledgered(
        Answering(Usage(1, 1)),
        JobContext(db, job_id=leaf["id"]),
        role="condense",
        provider="anthropic",
    )

    ledgered.complete(_request())

    [row] = _calls(db)
    assert leaf["started_by"] == "ana"
    assert (row["job_id"], row["run_id"], row["started_by"]) == (
        leaf["id"],
        parent,
        "ana",
    )


def test_an_enqueued_child_takes_its_parents_starter(db: Database) -> None:
    root = enqueue(db, "noop", {}, started_by="ana")
    child = enqueue(db, "noop", {}, parent_id=root)
    grandchild = enqueue(db, "noop", {}, parent_id=child)
    ledgered = Ledgered(
        Answering(Usage(1, 1)),
        JobContext(db, job_id=grandchild),
        role="r",
        provider="p",
    )

    ledgered.complete(_request())

    with db.connect() as conn:
        starter = conn.execute(
            "SELECT started_by FROM jobs WHERE id = ?", (child,)
        ).fetchone()[0]
    [row] = _calls(db)
    assert starter == "ana"
    assert (row["run_id"], row["started_by"]) == (root, "ana")


def test_a_concurrent_pool_loses_no_rows(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the REAL pool over a REAL pooled database: eight calls in flight, each
    # writing its row from its own thread on its own connection.
    monkeypatch.setenv(pool.ENV_WIDTH, "8")
    monkeypatch.setattr(packed, "PACK_ITEMS", 1)  # one row per section
    with db.write() as conn:
        register_text_model(conn)
        register_condense_prompt(conn)
        for n in range(40):
            add_section(conn, f"f{n}.py", f"def f{n}(): pass\n".encode(), n)
    overlap = Overlap(hold=0.02)

    outcome = condense(job(), JobContext(db, job_id="c1"), client=overlap)

    assert overlap.peak > 1
    assert outcome["condensed"] == 40
    rows = _calls(db)
    assert len(rows) == 40
    assert {row["role"] for row in rows} == {"condense"}


def test_every_provider_the_table_builds_is_recorded(
    db: Database, tmp_path: Path
) -> None:
    # a provider added to the map is wrapped without anyone remembering to
    context = job_context(db, tmp_path)
    with db.write() as conn:
        for name in providers._PROVIDERS:  # noqa: SLF001
            registry_store.insert(
                conn,
                "connections",
                name,
                json.dumps({"name": name, "provider": name, "auth": {}}),
                None,
                "t",
            )
    for name in providers._PROVIDERS:  # noqa: SLF001
        model = {**MODEL, "connection": name}
        try:
            built = providers.client_for(context, model, "brief")
        except LLMError:
            # anthropic needs a cipher to build; the wrapping is what matters
            built = providers.client_for(
                JobContext(db, object()),  # type: ignore[arg-type]
                model,
                "brief",
            )
        assert isinstance(built, Ledgered), name


def test_no_module_builds_a_provider_client_past_the_table() -> None:
    # the other way to bypass the ledger: construct a client directly
    clients = {
        node.name
        for module in (client, claude_code, openai)
        for node in ast.walk(ast.parse(Path(module.__file__).read_text()))
        if isinstance(node, ast.ClassDef)
        and any(
            isinstance(item, ast.FunctionDef) and item.name == "complete"
            for item in node.body
        )
    }
    builders = {
        path.relative_to(SRC).as_posix()
        for path in SRC.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text()))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in clients
    }

    assert clients >= {"AnthropicClient", "ClaudeCodeClient", "OpenAIClient"}
    assert builders == {"llm/providers.py"}


def test_an_embedding_pass_is_recorded_per_batch(db: Database) -> None:
    def local(name: str) -> object:
        return lambda texts: [[0.0] for _ in texts]

    config = {"name": "vectors", "kind": "embedding", "model": "mini-lm"}
    encode = encoder_for_model(JobContext(db, job_id="e1"), config, local)

    encode(["a", "b"])
    encode(["c"])

    rows = _calls(db)
    assert [
        (r["model"], r["role"], r["provider"], r["upstream_model"])
        for r in rows
    ] == [("vectors", "embedding", "local", "mini-lm")] * 2
    assert {(r["input_tokens"], r["ok"]) for r in rows} == {(None, 1)}


def test_a_failed_embedding_batch_is_recorded(db: Database) -> None:
    def local(name: str) -> object:
        def encode(texts: list[str]) -> list[list[float]]:
            raise RuntimeError("model fell over")

        return encode

    config = {"name": "vectors", "kind": "embedding", "model": "mini-lm"}
    encode = encoder_for_model(JobContext(db), config, local)

    with pytest.raises(RuntimeError):
        encode(["a"])

    assert [r["ok"] for r in _calls(db)] == [0]


def test_claude_code_reports_its_cache_and_upstream_model() -> None:
    payload = {
        "subtype": "success",
        "result": "ok",
        "usage": {
            "input_tokens": 2,
            "output_tokens": 5371,
            "cache_read_input_tokens": 300,
            "cache_creation_input_tokens": 14563,
        },
        "modelUsage": {
            "claude-haiku-4-5": {"outputTokens": 3},
            "claude-sonnet-4-5": {"outputTokens": 5368},
        },
    }

    usage = claude_code._read(payload).usage  # noqa: SLF001

    assert usage == Usage(2, 5371, 300, 14563, "claude-sonnet-4-5")


def test_openai_counts_cached_prompt_tokens_apart_from_input() -> None:
    payload = {
        "model": "gpt-5-2026-01-01",
        "choices": [{"message": {"content": "ok"}}],
        "usage": {
            "prompt_tokens": 1000,
            "completion_tokens": 10,
            "prompt_tokens_details": {"cached_tokens": 800},
        },
    }

    usage = openai._completion(payload).usage  # noqa: SLF001

    assert usage == Usage(200, 10, 800, None, "gpt-5-2026-01-01")


def test_the_anthropic_sdk_reports_its_cache_and_upstream_model() -> None:
    class Block:
        text = "ok"

    class Counts:
        input_tokens = 4
        output_tokens = 6
        cache_read_input_tokens = 100
        cache_creation_input_tokens = 50

    class Response:
        content = [Block()]
        usage = Counts()
        model = "claude-sonnet-5-20260101"

    usage = client._read(Response()).usage  # noqa: SLF001

    assert usage == Usage(4, 6, 100, 50, "claude-sonnet-5-20260101")


def test_a_provider_that_reports_no_cache_leaves_it_unknown() -> None:
    payload = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 1},
    }

    usage = openai._completion(payload).usage  # noqa: SLF001

    assert (usage.cache_read, usage.cache_creation) == (None, None)


API = "api"
PAGE = "page"


@pytest.mark.parametrize(
    ("door", "path", "body", "jobs"),
    [
        pytest.param(API, "/trees/default/sync", None, 1, id="api-sync"),
        pytest.param(API, "/trees/default/maintain", None, 1, id="maintain"),
        pytest.param(API, "/jobs", {"op": "noop"}, 1, id="api-job"),
        pytest.param(
            API,
            "/jobs",
            {"op": "sync", "scope": {"type": "all"}, "tree": "default"},
            3,
            id="api-fan-out",
        ),
        pytest.param(PAGE, "/ui/trees/default/sync", None, 1, id="page-sync"),
        pytest.param(
            PAGE, "/ui/jobs/run?tree=default", {"op": "noop"}, 1, id="page-job"
        ),
        pytest.param(
            PAGE,
            "/ui/jobs/run?tree=default",
            {"op": "sync"},
            3,
            id="page-fan-out",
        ),
    ],
)
def test_every_way_to_start_a_run_records_who_started_it(
    tmp_path: Path,
    door: str,
    path: str,
    body: dict[str, object] | None,
    jobs: int,
) -> None:
    # the per-user spend and a run's "who started it" read this on every
    # path; a path that forgets it reads as nobody
    key = Fernet.generate_key()
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, key)
    token = create_user(conn, "ana", "admin")[1]
    for name in ("alpha", "beta"):
        registry_store.insert(
            conn, "sources", name, json.dumps({"name": name}), None, "t"
        )
    app = create_app(connection=conn, master_key=key, key_id=1)
    with TestClient(app) as http:
        app.state.worker.stop()
        app.state.worker.join(timeout=5)
        if door == API:
            answer = http.post(
                path, json=body, headers={"Authorization": f"Bearer {token}"}
            )
        else:
            http.post("/ui/login", data={"token": token})
            answer = http.post(path, data=body, follow_redirects=False)
        starters = [
            row["started_by"]
            for row in conn.execute("SELECT started_by FROM jobs").fetchall()
        ]
    conn.close()

    assert answer.status_code in (200, 201, 303)
    assert starters == ["ana"] * jobs
