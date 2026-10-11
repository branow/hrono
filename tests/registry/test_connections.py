from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.registry.validation import connection_validation
from hrono.server.app import create_app

KEY = Fernet.generate_key()


# Built rather than written, so this file holds no literal that a secret
# scanner can mistake for a real key.
API_KEY = "not-a-key-" + "x" * 8


@pytest.fixture(autouse=True)
def _valid_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep provider validation offline: every key reports as valid (200).

    Both runners are patched: anthropic authenticates with `x-api-key` and the
    openai-shaped providers with a bearer header, so they have different
    defaults and a test that patched only one would reach the network
    for the other.
    """
    for name in ("_get", "_bearer_get"):
        monkeypatch.setattr(
            connection_validation, name, lambda url, key, timeout: 200
        )


ANTHROPIC = {
    "name": "anthropic-main",
    "provider": "anthropic",
    "auth": {"method": "api-key", "key": API_KEY},
}
OPENAI = {
    "name": "openai-main",
    "provider": "openai",
    "auth": {"method": "api-key", "key": API_KEY},
}
LOCAL = {
    "name": "ollama",
    "provider": "openai-compatible",
    "endpoint": "http://localhost:11434/v1",
    "auth": {"method": "none"},
}
CLAUDE_CODE = {
    "name": "cc",
    "provider": "claude-code",
    "auth": {"method": "none"},
}


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
        yield Harness(client, conn, tokens)
    conn.close()


def post(harness: Harness, body: dict, role: str = "writer") -> object:
    return harness.client.post(
        "/connections", json=body, headers=harness.auth(role)
    )


@pytest.mark.parametrize("body", [ANTHROPIC, OPENAI, LOCAL, CLAUDE_CODE])
def test_registers_each_provider_shape(harness: Harness, body: dict) -> None:
    assert post(harness, body).status_code == 201
    fetched = harness.client.get(
        f"/connections/{body['name']}", headers=harness.auth("reader")
    )
    assert fetched.status_code == 200
    assert fetched.json()["provider"] == body["provider"]


def test_api_key_encrypted_and_masked(harness: Harness) -> None:
    post(harness, ANTHROPIC)
    fetched = harness.client.get(
        "/connections/anthropic-main", headers=harness.auth("reader")
    )
    assert fetched.json()["auth"]["key"] == "***"
    assert API_KEY not in fetched.text

    row = harness.conn.execute(
        "SELECT config, key_id FROM registry "
        "WHERE collection = 'connections' AND name = 'anthropic-main'"
    ).fetchone()
    assert API_KEY not in row["config"]
    assert row["key_id"] == 1


def test_none_auth_stores_no_secret(harness: Harness) -> None:
    post(harness, CLAUDE_CODE)
    row = harness.conn.execute(
        "SELECT key_id FROM registry WHERE name = 'cc'"
    ).fetchone()
    assert row["key_id"] is None


def test_unknown_provider_is_422(harness: Harness) -> None:
    bad = {"name": "x", "provider": "cohere", "auth": {"method": "none"}}
    assert post(harness, bad).status_code == 422


def test_missing_api_key_is_422(harness: Harness) -> None:
    bad = {"name": "x", "provider": "anthropic", "auth": {"method": "api-key"}}
    assert post(harness, bad).status_code == 422
