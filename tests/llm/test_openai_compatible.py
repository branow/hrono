"""#152: a local openai-shaped server, at a declared endpoint.

The provider is #151's client with two differences, and these pin both: the
endpoint is REQUIRED (a local server has no default address), and there may be
no key at all (the usual case for ollama, vllm and lm-studio). The server here
is a real one on a real socket, which is the whole argument for riding the REST
shape rather than an SDK.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from pydantic import ValidationError

from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database
from hrono.embed.encoders import encoder_for_model
from hrono.jobs.ops import JobContext
from hrono.llm.client import CompletionRequest, LLMError
from hrono.llm.openai import OpenAIClient, credential
from hrono.llm.providers import client_for
from hrono.registry import store as registry_store
from hrono.registry.connections import Connection

KEY = Fernet.generate_key()


class _Handler(BaseHTTPRequestHandler):
    responses: dict[str, tuple[int, object]] = {}
    requests: list[tuple[str, dict]] = []

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's name
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        _Handler.requests.append((self.path, dict(self.headers)))
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
def local() -> Iterator[str]:
    _Handler.responses = {}
    _Handler.requests = []
    server = HTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1"
    finally:
        server.shutdown()
        server.server_close()


@pytest.fixture
def db(tmp_path: Path) -> Iterator[tuple[Database, Cipher]]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        key_id = reconcile(conn, KEY).key_id
    yield database, Cipher.from_key(KEY, key_id)
    database.close()


def _keyless(db: tuple[Database, Cipher], endpoint: str) -> None:
    database, _cipher = db
    with database.connect() as conn:
        registry_store.insert(
            conn,
            "connections",
            "local",
            json.dumps(
                {
                    "name": "local",
                    "provider": "openai-compatible",
                    "endpoint": endpoint,
                    "auth": {"method": "none"},
                }
            ),
            None,
            "t",
        )


def _model(kind: str) -> dict[str, object]:
    return {
        "name": "m",
        "kind": kind,
        "connection": "local",
        "model": "llama3",
        "params": {},
    }


def test_a_completion_works_with_no_key_at_all(
    local: str, db: tuple[Database, Cipher]
) -> None:
    database, cipher = db
    _keyless(db, local)
    _Handler.responses = {
        "/v1/chat/completions": (
            200,
            {
                "choices": [{"message": {"content": "local answer"}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            },
        )
    }

    result = OpenAIClient(database, cipher).complete(
        CompletionRequest(_model("text"), "", "ask")
    )

    assert result.text == "local answer"
    _path, headers = _Handler.requests[0]
    assert "Authorization" not in headers  # nothing to send, nothing sent


def test_the_endpoint_is_where_the_call_goes(
    local: str, db: tuple[Database, Cipher]
) -> None:
    database, cipher = db
    _keyless(db, local)

    key, base = credential(database, cipher, "local")

    assert key is None
    assert base == local  # never api.openai.com


def test_an_endpoint_with_or_without_v1_reaches_the_same_place(
    local: str, db: tuple[Database, Cipher]
) -> None:
    # ollama's own docs give `http://localhost:11434/v1`; a proxy is usually a
    # bare host. Posting to `/v1/v1/chat/completions` for half the users is not
    # an acceptable way to find out which one someone pasted.
    database, cipher = db
    _Handler.responses = {
        "/v1/chat/completions": (
            200,
            {"choices": [{"message": {"content": "ok"}}]},
        )
    }
    _keyless(db, local)
    for endpoint in (local, local.removesuffix("/v1")):
        with database.write() as conn:
            conn.execute(
                "UPDATE registry SET config = ? WHERE name = 'local'",
                (
                    json.dumps(
                        {
                            "name": "local",
                            "provider": "openai-compatible",
                            "endpoint": endpoint,
                            "auth": {"method": "none"},
                        }
                    ),
                ),
            )
        result = OpenAIClient(database, cipher).complete(
            CompletionRequest(_model("text"), "", "ask")
        )
        assert result.text == "ok"

    assert [path for path, _headers in _Handler.requests] == [
        "/v1/chat/completions",
        "/v1/chat/completions",
    ]


def test_an_embedding_model_embeds_against_the_same_server(
    local: str, db: tuple[Database, Cipher], tmp_path: Path
) -> None:
    database, cipher = db
    _keyless(db, local)
    _Handler.responses = {
        "/v1/embeddings": (
            200,
            {"data": [{"index": 0, "embedding": [0.25, 0.75]}]},
        )
    }

    encode = encoder_for_model(
        JobContext(database, cipher, tmp_path / "cache"),
        _model("embedding"),
        lambda model_id: None,
    )

    assert encode(["only"]) == [[0.25, 0.75]]


def test_a_server_that_is_not_running_is_one_clean_error(
    db: tuple[Database, Cipher],
) -> None:
    database, cipher = db
    _keyless(db, "http://127.0.0.1:9/v1")  # discard port: refuses at once

    with pytest.raises(LLMError, match="cannot reach the model server"):
        OpenAIClient(database, cipher).complete(
            CompletionRequest(_model("text"), "", "ask")
        )


def test_the_provider_table_serves_an_openai_compatible_connection(
    local: str, db: tuple[Database, Cipher], tmp_path: Path
) -> None:
    database, cipher = db
    _keyless(db, local)

    client = client_for(
        JobContext(database, cipher, tmp_path / "cache"), _model("text")
    )

    assert isinstance(client, OpenAIClient)


def test_a_connection_without_an_endpoint_is_refused_by_the_model() -> None:
    # confirmed rather than assumed: there is no default address for a local
    # server, so the field is required at the boundary and the call site never
    # has to guess one.
    with pytest.raises(ValidationError):
        Connection.model_validate(
            {
                "name": "local",
                "provider": "openai-compatible",
                "auth": {"method": "none"},
            }
        )

    ok = Connection.model_validate(
        {
            "name": "local",
            "provider": "openai-compatible",
            "endpoint": "http://127.0.0.1:11434/v1",
            "auth": {"method": "none"},
        }
    )
    assert ok.root.endpoint == "http://127.0.0.1:11434/v1"  # type: ignore[union-attr]
