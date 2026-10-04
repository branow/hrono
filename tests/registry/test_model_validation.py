import json
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.registry import store
from hrono.registry.descriptor import ValidationContext, ValidationFailed
from hrono.registry.validation.model_validation import validate_model

KEY = Fernet.generate_key()
# built, not written: a literal here blocks every tool (#153)
API_KEY = "not-a-key-" + "x" * 8


def context(
    tmp_path: Path, *, with_connection: bool = True
) -> ValidationContext:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    cipher = Cipher.from_key(KEY, 1)
    if with_connection:
        secret = cipher.encrypt(API_KEY)
        payload = {
            "name": "prov",
            "provider": "anthropic",
            "auth": {"method": "api-key", "key": secret.ciphertext},
        }
        store.insert(conn, "connections", "prov", json.dumps(payload), 1, "now")
    return ValidationContext(database=Database.adopt(conn), cipher=cipher)


def embedding(dims: int = 4, connection: str | None = None) -> dict:
    return {
        "name": "e",
        "kind": "embedding",
        "connection": connection,
        "model": "m",
        "params": {"dims": dims},
    }


def text(connection: str | None = "prov") -> dict:
    return {"name": "t", "kind": "text", "connection": connection, "model": "m"}


def test_embedding_dims_ok(tmp_path: Path) -> None:
    validate_model(
        embedding(dims=4),
        context(tmp_path),
        embed=lambda cfg, conn, t: [0.0, 0.0, 0.0, 0.0],
    )


def test_embedding_dims_mismatch_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationFailed) as caught:
        validate_model(
            embedding(dims=4),
            context(tmp_path),
            embed=lambda cfg, conn, t: [0.0, 0.0],
        )
    assert "dims" in str(caught.value)


def test_text_round_trip_ok(tmp_path: Path) -> None:
    validate_model(
        text(),
        context(tmp_path),
        generate=lambda cfg, conn, t: "hello",
    )


def test_text_empty_response_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationFailed):
        validate_model(
            text(), context(tmp_path), generate=lambda cfg, conn, t: "   "
        )


def test_connection_failure_is_rejected(tmp_path: Path) -> None:
    def boom(cfg: dict, conn: dict, t: float) -> str:
        raise ConnectionError("refused")

    with pytest.raises(ValidationFailed) as caught:
        validate_model(text(), context(tmp_path), generate=boom)
    assert "reach" in str(caught.value)


def test_unknown_connection_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationFailed) as caught:
        validate_model(
            text(connection="ghost"),
            context(tmp_path),
            generate=lambda cfg, conn, t: "hi",
        )
    assert "unknown connection" in str(caught.value)


def test_resolved_connection_is_decrypted_for_the_probe(tmp_path: Path) -> None:
    seen: dict = {}

    def generate(cfg: dict, connection: dict, t: float) -> str:
        seen["key"] = connection["auth"]["key"]
        return "ok"

    validate_model(text(), context(tmp_path), generate=generate)
    assert seen["key"] == API_KEY


def test_credential_never_appears_in_a_reason(tmp_path: Path) -> None:
    def boom(cfg: dict, connection: dict, t: float) -> str:
        raise ConnectionError(connection["auth"]["key"])

    with pytest.raises(ValidationFailed) as caught:
        validate_model(text(), context(tmp_path), generate=boom)
    assert API_KEY not in str(caught.value)


def test_text_without_connection_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValidationFailed):
        validate_model(
            text(connection=None),
            context(tmp_path, with_connection=False),
            generate=lambda cfg, conn, t: "hi",
        )


def test_a_local_endpoint_is_probed_at_its_own_root(tmp_path: Path) -> None:
    """The defect a live drive caught (#153): a working local server refused.

    `endpoint` may already name the `/v1` root — ollama's own docs give one —
    and appending another probed `/v1/v1/chat/completions`, which every such
    server answers with a 404. The model then could not be registered against a
    connection that had just validated successfully.
    """
    import httpx

    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    cipher = Cipher.from_key(KEY, 1)
    store.insert(
        conn,
        "connections",
        "local",
        json.dumps(
            {
                "name": "local",
                "provider": "openai-compatible",
                "endpoint": "http://127.0.0.1:11434/v1",
                "auth": {"method": "none"},
            }
        ),
        None,
        "now",
    )
    ctx = ValidationContext(database=Database.adopt(conn), cipher=cipher)

    seen: list[str] = []

    class _Response:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {"choices": [{"message": {"content": "ok"}}]}

    def post(url: str, **kwargs: object) -> object:
        seen.append(url)
        return _Response()

    original = httpx.post
    httpx.post = post  # type: ignore[assignment]
    try:
        validate_model(
            {
                "name": "t",
                "kind": "text",
                "connection": "local",
                "model": "llama3",
            },
            ctx,
        )
    finally:
        httpx.post = original  # type: ignore[assignment]

    assert seen == ["http://127.0.0.1:11434/v1/chat/completions"]


def test_a_missing_embedding_backend_says_how_to_install_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)

    with pytest.raises(ValidationFailed) as caught:
        validate_model(embedding(), context(tmp_path, with_connection=False))

    assert "uv sync --extra embed" in str(caught.value)
    assert "hrono[embed]" in str(caught.value)
