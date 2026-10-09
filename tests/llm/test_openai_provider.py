"""The openai provider — completions and embeddings over real HTTP.

Both halves are driven against a local server on a real socket: the
whole reason this rides httpx rather than an SDK is that ollama, vllm and
lm-studio speak the same REST shape, and a mocked client object would prove
none of it.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database
from hrono.embed.encoders import encoder_for_model
from hrono.embed.runner import EmbedError
from hrono.jobs.ops import JobContext
from hrono.jobs.worker import enqueue
from hrono.llm.client import CompletionRequest, LLMError
from hrono.llm.openai import OpenAIClient, embeddings
from hrono.llm.providers import client_for
from hrono.registry import store as registry_store
from hrono.usage.rollup import usage
from tests.stub_server import serving

KEY = Fernet.generate_key()
SECRET = "s" * 20  # stands in for the api credential; never a real one


class _Handler(BaseHTTPRequestHandler):
    responses: dict[str, tuple[int, object]] = {}
    requests: list[tuple[str, dict, dict]] = []

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's name
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        _Handler.requests.append((self.path, dict(self.headers), body))
        status, payload = _Handler.responses.get(self.path, (404, {}))
        raw = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args: object) -> None:
        return


@pytest.fixture
def server() -> Iterator[str]:
    _Handler.responses = {}
    _Handler.requests = []
    with serving(_Handler) as base:
        yield base


@pytest.fixture
def db(tmp_path: Path) -> Iterator[tuple[Database, Cipher]]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        key_id = reconcile(conn, KEY).key_id
    yield database, Cipher.from_key(KEY, key_id)
    database.close()


def _connection(
    db: tuple[Database, Cipher],
    name: str,
    provider: str,
    endpoint: str | None,
    *,
    keyed: bool = True,
) -> None:
    database, cipher = db
    config: dict[str, object] = {
        "name": name,
        "provider": provider,
        "endpoint": endpoint,
    }
    key_id = None
    if keyed:
        secret = cipher.encrypt(SECRET)
        config["auth"] = {"method": "api-key", "key": secret.ciphertext}
        key_id = secret.key_id
    else:
        config["auth"] = {"method": "none"}
    with database.connect() as conn:
        registry_store.insert(
            conn, "connections", name, json.dumps(config), key_id, "t"
        )


def _model(kind: str, connection: str | None) -> dict[str, object]:
    return {
        "name": "m",
        "kind": kind,
        "connection": connection,
        "model": "a-model",
        "params": {"max_tokens": 64},
    }


def test_a_completion_goes_over_the_wire_and_counts_its_tokens(
    server: str, db: tuple[Database, Cipher]
) -> None:
    database, cipher = db
    _connection(db, "oa", "openai", server)
    _Handler.responses = {
        "/v1/chat/completions": (
            200,
            {
                "choices": [{"message": {"content": "the answer"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 3},
            },
        )
    }

    result = OpenAIClient(database, cipher).complete(
        CompletionRequest(_model("text", "oa"), "be terse", "the question")
    )

    assert result.text == "the answer"
    assert (result.usage.input_tokens, result.usage.output_tokens) == (11, 3)
    path, headers, body = _Handler.requests[0]
    assert path == "/v1/chat/completions"
    assert headers["Authorization"] == f"Bearer {SECRET}"
    assert body["messages"] == [
        {"role": "system", "content": "be terse"},
        {"role": "user", "content": "the question"},
    ]
    assert body["max_tokens"] == 64  # the model's params, not a default


def test_embeddings_come_back_in_the_inputs_order(
    server: str, db: tuple[Database, Cipher]
) -> None:
    # the api does not promise response order; a silently reordered batch would
    # attach every chunk to its neighbour's meaning.
    database, cipher = db
    _connection(db, "oa", "openai", server)
    _Handler.responses = {
        "/v1/embeddings": (
            200,
            {
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
        )
    }

    encode = embeddings(database, cipher, _model("embedding", "oa"))
    vectors = encode(["first", "second"])  # type: ignore[operator]

    assert vectors == [[1.0, 0.0], [0.0, 1.0]]
    _path, _headers, body = _Handler.requests[0]
    assert body["input"] == ["first", "second"]


def test_a_short_or_ragged_batch_is_refused(
    server: str, db: tuple[Database, Cipher]
) -> None:
    database, cipher = db
    _connection(db, "oa", "openai", server)
    _Handler.responses = {
        "/v1/embeddings": (200, {"data": [{"index": 0, "embedding": [1.0]}]})
    }

    encode = embeddings(database, cipher, _model("embedding", "oa"))
    with pytest.raises(LLMError, match="wrong vector count"):
        encode(["first", "second"])  # type: ignore[operator]


def test_refused_credentials_and_transport_failures_are_one_error(
    server: str, db: tuple[Database, Cipher]
) -> None:
    database, cipher = db
    _connection(db, "oa", "openai", server)
    _Handler.responses = {"/v1/chat/completions": (401, {"error": "nope"})}
    request = CompletionRequest(_model("text", "oa"), "", "hi")

    with pytest.raises(LLMError, match="refused the credentials"):
        OpenAIClient(database, cipher).complete(request)

    _connection(db, "dead", "openai", "http://127.0.0.1:9")
    with pytest.raises(LLMError, match="cannot reach"):
        OpenAIClient(database, cipher).complete(
            CompletionRequest(_model("text", "dead"), "", "hi")
        )


def test_a_malformed_body_is_one_error_not_a_crash(
    server: str, db: tuple[Database, Cipher]
) -> None:
    database, cipher = db
    _connection(db, "oa", "openai", server)
    _Handler.responses = {"/v1/chat/completions": (200, {"choices": []})}

    with pytest.raises(LLMError, match="no choices"):
        OpenAIClient(database, cipher).complete(
            CompletionRequest(_model("text", "oa"), "", "hi")
        )


def test_no_key_material_appears_in_any_error(
    server: str, db: tuple[Database, Cipher]
) -> None:
    database, cipher = db
    _connection(db, "oa", "openai", server)
    _Handler.responses = {"/v1/chat/completions": (500, {})}

    with pytest.raises(LLMError) as raised:
        OpenAIClient(database, cipher).complete(
            CompletionRequest(_model("text", "oa"), "", "hi")
        )

    assert SECRET not in str(raised.value)


def test_the_provider_table_resolves_an_openai_connection(
    server: str, db: tuple[Database, Cipher], tmp_path: Path
) -> None:
    database, cipher = db
    _connection(db, "oa", "openai", server)
    context = JobContext(database, cipher, tmp_path / "cache")

    client = client_for(context, _model("text", "oa"), "brief")

    assert isinstance(client.inner, OpenAIClient)  # type: ignore[attr-defined]


def test_an_embedding_model_with_no_connection_still_loads_locally(
    db: tuple[Database, Cipher], tmp_path: Path
) -> None:
    # the injectable local seam must keep meaning what it meant.
    database, cipher = db
    loaded: list[str] = []

    def local(model_id: str):
        loaded.append(model_id)
        return lambda texts: [[0.0] for _ in texts]

    encode = encoder_for_model(
        JobContext(database, cipher, tmp_path / "cache"),
        _model("embedding", None),
        local,
    )

    assert loaded == ["a-model"]
    assert encode(["x"]) == [[0.0]]


def test_an_embedding_model_on_a_connection_goes_remote(
    server: str, db: tuple[Database, Cipher], tmp_path: Path
) -> None:
    database, cipher = db
    _connection(db, "oa", "openai", server)
    _Handler.responses = {
        "/v1/embeddings": (
            200,
            {"data": [{"index": 0, "embedding": [0.5, 0.5]}]},
        )
    }

    def local(model_id: str):
        raise AssertionError("a remote model must not load in process")

    encode = encoder_for_model(
        JobContext(database, cipher, tmp_path / "cache"),
        _model("embedding", "oa"),
        local,
    )

    assert encode(["only"]) == [[0.5, 0.5]]


def test_a_provider_that_cannot_embed_says_so(
    db: tuple[Database, Cipher], tmp_path: Path
) -> None:
    database, cipher = db
    _connection(db, "cli", "claude-code", None, keyed=False)

    with pytest.raises(EmbedError, match="cannot serve an embedding"):
        encoder_for_model(
            JobContext(database, cipher, tmp_path / "cache"),
            _model("embedding", "cli"),
            lambda model_id: None,
        )


def test_a_remote_embedding_batch_records_the_tokens_the_provider_reports(
    server: str, db: tuple[Database, Cipher], tmp_path: Path
) -> None:
    # through the real encoder, the real HTTP exchange and the real
    # ledger, then the roll-up that prices it.
    database, cipher = db
    _connection(db, "oa", "openai", server)
    _Handler.responses = {
        "/v1/embeddings": (
            200,
            {
                "data": [{"index": 0, "embedding": [0.5]}],
                "usage": {
                    "prompt_tokens": 1_000_000,
                    "total_tokens": 1_000_000,
                },
            },
        )
    }
    model = {
        **_model("embedding", "oa"),
        "model": "text-embedding-3-small",
        "price": {"input": 0.02, "output": 0.0},
    }
    with database.connect() as conn, conn:
        registry_store.insert(conn, "models", "m", json.dumps(model), None, "t")
    run = enqueue(database, "embed", {}, started_by="ana")
    encode = encoder_for_model(
        JobContext(database, cipher, tmp_path / "cache", job_id=run),
        model,
        lambda model_id: None,
    )

    encode(["a"])
    encode(["b"])

    with database.connect() as conn:
        [group] = usage(conn, "run")
    assert group["tokens"]["input"] == 2_000_000
    assert group["cost"]["metered"] == {"usd": 0.04, "unpriced": []}


def test_a_local_embedding_batch_still_records_no_tokens(
    db: tuple[Database, Cipher], tmp_path: Path
) -> None:
    database, cipher = db
    run = enqueue(database, "embed", {}, started_by="ana")
    encode = encoder_for_model(
        JobContext(database, cipher, tmp_path / "cache", job_id=run),
        _model("embedding", None),
        lambda model_id: lambda texts: [[0.0] for _ in texts],
    )

    encode(["a"])

    with database.connect() as conn:
        row = conn.execute("SELECT input_tokens FROM llm_calls").fetchone()
    assert row["input_tokens"] is None
