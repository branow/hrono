from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.registry.validation import connection_validation, model_validation
from hrono.server.app import create_app

KEY = Fernet.generate_key()

CONNECTION = {
    "name": "anthropic-main",
    "provider": "anthropic",
    "auth": {"method": "api-key", "key": "sk-secret"},
}
TEXT = {
    "name": "opus",
    "kind": "text",
    "connection": "anthropic-main",
    "model": "claude-opus-4-8",
    "params": {"temperature": 0.2, "max_tokens": 1024},
}
EMBEDDING = {
    "name": "local-embed",
    "kind": "embedding",
    "connection": None,
    "model": "BAAI/bge-small",
    "params": {"dims": 384, "batch_size": 32},
}


@pytest.fixture(autouse=True)
def _valid_backends(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep validation offline: auth ok, probes behave as declared."""
    monkeypatch.setattr(
        connection_validation, "_get", lambda url, key, timeout: 200
    )
    monkeypatch.setattr(
        model_validation,
        "_default_embed",
        lambda config, conn, t: (
            [0.0] * int((config.get("params") or {})["dims"])
        ),
    )
    monkeypatch.setattr(
        model_validation, "_default_generate", lambda config, conn, t: "ok"
    )


class Harness:
    def __init__(self, client: TestClient, conn: object, tokens: dict) -> None:
        self.client = client
        self.conn = conn
        self.tokens = tokens

    def auth(self, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[role]}"}


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        client.post(
            "/connections",
            json=CONNECTION,
            headers={"Authorization": f"Bearer {tokens['writer']}"},
        )
        yield Harness(client, conn, tokens)
    conn.close()


def post(harness: Harness, body: dict, role: str = "writer") -> object:
    return harness.client.post("/models", json=body, headers=harness.auth(role))


@pytest.mark.parametrize("body", [TEXT, EMBEDDING])
def test_registers_text_and_embedding(harness: Harness, body: dict) -> None:
    assert post(harness, body).status_code == 201
    fetched = harness.client.get(
        f"/models/{body['name']}", headers=harness.auth("reader")
    )
    assert fetched.status_code == 200
    got = fetched.json()
    assert got["kind"] == body["kind"]
    assert got["connection"] == body["connection"]
    assert got["params"] == body["params"]


def test_bad_kind_is_422(harness: Harness) -> None:
    bad = {"name": "x", "kind": "vision", "model": "m"}
    assert post(harness, bad).status_code == 422
