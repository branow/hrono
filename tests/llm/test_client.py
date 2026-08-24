import json
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.llm.client import (
    AnthropicClient,
    CompletionRequest,
    LLMError,
    Usage,
)
from hrono.registry import store

PLAINTEXT_KEY = "sk-ant-secret-value"
CONNECTION = "anthropic-prod"


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database(open_database(tmp_path / "hrono.db"))  # type: ignore[operator]
    yield database
    database.close()


@pytest.fixture
def ciph(db: Database) -> Cipher:
    key = Fernet.generate_key()
    with db.connect() as conn:
        record = reconcile(conn, key)
    return Cipher.from_key(key, record.key_id)


def register_connection(
    conn: object, ciph: Cipher, key: str = PLAINTEXT_KEY
) -> str:
    secret = ciph.encrypt(key)
    config = {
        "provider": "anthropic",
        "auth": {"key": secret.ciphertext},
        "endpoint": None,
    }
    store.insert(
        conn,  # type: ignore[arg-type]
        "connections",
        CONNECTION,
        json.dumps(config),
        secret.key_id,
        "t",
    )
    return secret.ciphertext


def text_model(max_tokens: int | None = 256) -> dict[str, object]:
    params: dict[str, object] = {}
    if max_tokens is not None:
        params["max_tokens"] = max_tokens
    return {
        "name": "sonnet",
        "kind": "text",
        "connection": CONNECTION,
        "model": "claude-sonnet-5",
        "params": params,
    }


def fake_response(text: str, input_tokens: int, output_tokens: int) -> object:
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(
            input_tokens=input_tokens, output_tokens=output_tokens
        ),
    )


def capturing_invoke(captured: dict[str, object], response: object):
    def invoke(**kwargs: object) -> object:
        captured.update(kwargs)
        return response

    return invoke


def test_returns_text_and_usage(db: Database, ciph: Cipher) -> None:
    with db.connect() as conn:
        register_connection(conn, ciph)
    invoke = capturing_invoke({}, fake_response("a brief.", 120, 34))
    client = AnthropicClient(db, ciph, invoke=invoke)
    result = client.complete(
        CompletionRequest(text_model(), system="Summarise.", content="body")
    )
    assert result.text == "a brief."
    assert result.usage == Usage(input_tokens=120, output_tokens=34)


def test_api_key_is_read_only_via_the_cipher(
    db: Database, ciph: Cipher
) -> None:
    with db.connect() as conn:
        ciphertext = register_connection(conn, ciph)
    captured: dict[str, object] = {}
    client = AnthropicClient(
        db, ciph, invoke=capturing_invoke(captured, fake_response("x", 1, 1))
    )
    client.complete(CompletionRequest(text_model(), system="", content="c"))
    # the client passed the DECRYPTED key to the SDK, and the stored form was
    # the ciphertext, not the plaintext.
    assert captured["api_key"] == PLAINTEXT_KEY
    assert ciphertext != PLAINTEXT_KEY


def test_max_tokens_from_params_then_default(
    db: Database, ciph: Cipher
) -> None:
    with db.connect() as conn:
        register_connection(conn, ciph)
    captured: dict[str, object] = {}
    client = AnthropicClient(
        db, ciph, invoke=capturing_invoke(captured, fake_response("x", 1, 1))
    )
    client.complete(CompletionRequest(text_model(512), system="", content="c"))
    assert captured["max_tokens"] == 512
    client.complete(CompletionRequest(text_model(None), system="", content="c"))
    assert captured["max_tokens"] == 4096  # documented default


def test_missing_connection_raises_llmerror(db: Database, ciph: Cipher) -> None:
    model = text_model()
    model["connection"] = None
    client = AnthropicClient(db, ciph, invoke=capturing_invoke({}, None))
    with pytest.raises(LLMError, match="requires a connection"):
        client.complete(CompletionRequest(model, system="", content="c"))


def test_unknown_connection_raises_llmerror(db: Database, ciph: Cipher) -> None:
    client = AnthropicClient(db, ciph, invoke=capturing_invoke({}, None))
    with pytest.raises(LLMError, match="unknown connection"):
        client.complete(CompletionRequest(text_model(), system="", content="c"))


def test_connection_without_key_raises_llmerror(
    db: Database, ciph: Cipher
) -> None:
    with db.connect() as conn:
        store.insert(
            conn,
            "connections",
            CONNECTION,
            json.dumps({"provider": "anthropic", "auth": {}}),
            None,
            "t",
        )
    client = AnthropicClient(db, ciph, invoke=capturing_invoke({}, None))
    with pytest.raises(LLMError, match="no api key"):
        client.complete(CompletionRequest(text_model(), system="", content="c"))


def test_sdk_failure_becomes_a_clean_llmerror(
    db: Database, ciph: Cipher
) -> None:
    with db.connect() as conn:
        register_connection(conn, ciph)

    def boom(**kwargs: object) -> object:
        raise RuntimeError("transport exploded: sk-ant-secret-value")

    client = AnthropicClient(db, ciph, invoke=boom)
    with pytest.raises(LLMError) as excinfo:
        client.complete(CompletionRequest(text_model(), system="", content="c"))
    # the domain error message is client-safe: it does not leak the raw SDK
    # text (which here even contained the key).
    assert "sk-ant-secret-value" not in str(excinfo.value)
