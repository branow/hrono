from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.registry.descriptor import ValidationFailed
from hrono.registry.validation import connection_validation
from hrono.registry.validation.connection_validation import validate_connection
from hrono.server.app import create_app

KEY = Fernet.generate_key()
# built, not written: a literal here blocked three tickets (#153)
API_KEY = "not-a-key-" + "x" * 8


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


def test_a_provider_with_no_key_is_not_key_validated() -> None:
    # claude-code bills through the operator's own login; the CLI probe is its
    # validation instead.
    called = False

    def run(url: str, key: str, timeout: float) -> int:
        nonlocal called
        called = True
        return 200

    validate_connection(
        {"name": "cc", "provider": "claude-code", "auth": {"method": "none"}},
        run=run,
        probe=lambda: True,
    )
    assert called is False


def openai(**over: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "o",
        "provider": "openai",
        "auth": {"method": "api-key", "key": API_KEY},
    }
    body.update(over)
    return body


def local(**over: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": "l",
        "provider": "openai-compatible",
        "endpoint": "http://127.0.0.1:11434/v1",
        "auth": {"method": "none"},
    }
    body.update(over)
    return body


def test_an_openai_key_is_listed_against_the_models_endpoint() -> None:
    seen: list[str] = []

    def run(url: str, key: str, timeout: float) -> int:
        seen.append(url)
        return 200

    validate_connection(openai(), run=run)

    assert seen == ["https://api.openai.com/v1/models"]


def test_an_openai_key_that_is_refused_fails_the_write() -> None:
    with pytest.raises(ValidationFailed) as caught:
        validate_connection(openai(), run=lambda url, key, t: 401)
    assert "auth" in str(caught.value).lower()
    assert API_KEY not in str(caught.value)


def test_a_local_server_is_probed_at_its_own_endpoint() -> None:
    seen: list[str] = []

    def run(url: str, key: str, timeout: float) -> int:
        seen.append(url)
        return 200

    validate_connection(local(), run=run)

    assert seen == ["http://127.0.0.1:11434/v1/models"]


def test_a_local_server_that_is_not_running_is_rejected() -> None:
    with pytest.raises(ValidationFailed) as caught:
        validate_connection(local(), run=lambda url, key, t: 0)
    assert "reach" in str(caught.value)


def test_an_openai_compatible_connection_needs_an_endpoint() -> None:
    body = local()
    del body["endpoint"]

    with pytest.raises(ValidationFailed) as caught:
        validate_connection(body, run=lambda url, key, t: 200)

    assert "endpoint" in str(caught.value)


def test_each_provider_gets_the_runner_it_authenticates_with() -> None:
    # anthropic sends `x-api-key`, the openai-shaped ones a bearer header, so
    # they have DIFFERENT defaults. Resolved at call time, or patching one
    # would silently leave the other reaching the network.
    assert (
        connection_validation._default("anthropic")
        is connection_validation._get
    )
    for provider in ("openai", "openai-compatible"):
        assert (
            connection_validation._default(provider)
            is connection_validation._bearer_get
        )


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


def test_an_openai_write_is_rejected_when_the_key_is_refused(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the end this exists for: a dead connection must not register and fail
    # hours later at condense time.
    monkeypatch.setattr(
        connection_validation, "_bearer_get", lambda url, key, timeout: 401
    )

    response = harness.client.post(
        "/connections",
        json={
            "name": "o",
            "provider": "openai",
            "auth": {"method": "api-key", "key": API_KEY},
        },
        headers=harness.headers,
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
