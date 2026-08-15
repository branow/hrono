from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.registry import connection_validation
from hrono.registry.connection_validation import validate_connection
from hrono.registry.descriptor import ValidationFailed
from hrono.server.app import create_app

KEY = Fernet.generate_key()
API_KEY = "sk-donotleak"


def anthropic(**over: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "a",
        "provider": "anthropic",
        "auth": {"method": "api-key", "key": API_KEY},
    }
    body.update(over)
    return body


def test_valid_key_passes() -> None:
    validate_connection(anthropic(), run=lambda url, key, t: 200)


def test_rejected_key_is_auth_failure() -> None:
    with pytest.raises(ValidationFailed) as caught:
        validate_connection(anthropic(), run=lambda url, key, t: 401)
    assert "auth" in str(caught.value).lower()

    with pytest.raises(ValidationFailed):
        validate_connection(anthropic(), run=lambda url, key, t: 403)


def test_unreachable_endpoint_is_rejected() -> None:
    with pytest.raises(ValidationFailed) as caught:
        validate_connection(anthropic(), run=lambda url, key, t: 0)
    assert "reach" in str(caught.value)


def test_endpoint_override_is_used() -> None:
    seen: list[str] = []

    def run(url: str, key: str, timeout: float) -> int:
        seen.append(url)
        return 200

    validate_connection(anthropic(endpoint="https://proxy.example"), run=run)
    assert seen[0] == "https://proxy.example/v1/models"


def test_key_never_appears_in_reason() -> None:
    with pytest.raises(ValidationFailed) as caught:
        validate_connection(anthropic(), run=lambda url, key, t: 401)
    assert API_KEY not in str(caught.value)


def test_non_anthropic_provider_is_not_validated() -> None:
    called = False

    def run(url: str, key: str, timeout: float) -> int:
        nonlocal called
        called = True
        return 200

    validate_connection(
        {"name": "cc", "provider": "claude-code", "auth": {"method": "none"}},
        run=run,
    )
    assert called is False


class Harness:
    def __init__(self, client: TestClient, conn: object, token: str) -> None:
        self.client = client
        self.conn = conn
        self.headers = {"Authorization": f"Bearer {token}"}


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "writer", "writer")[1]
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Harness(client, conn, token)
    conn.close()


def test_write_rejected_when_provider_rejects_key(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        connection_validation, "_get", lambda url, key, timeout: 401
    )
    response = harness.client.post(
        "/connections", json=anthropic(), headers=harness.headers
    )
    assert response.status_code == 400
    assert (
        harness.conn.execute(
            "SELECT count(*) FROM registry WHERE collection = 'connections'"
        ).fetchone()[0]
        == 0
    )


def test_write_succeeds_when_provider_accepts_key(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        connection_validation, "_get", lambda url, key, timeout: 200
    )
    response = harness.client.post(
        "/connections", json=anthropic(), headers=harness.headers
    )
    assert response.status_code == 201
