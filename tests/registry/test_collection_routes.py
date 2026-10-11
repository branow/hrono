"""The routes every registry collection shares, run once per collection.

Each collection is served by the same `engine.build_router` with the same
write role, so CRUD and the role and error matrix are one test over all of
them. It stays parametrized because it is auth: a collection wired with the
wrong role must fail under its own name.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
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

# Built rather than written, so this file holds no literal that a secret
# scanner can mistake for a real key.
API_KEY = "not-a-key-" + "x" * 8

CONNECTION = {
    "name": "anthropic-main",
    "provider": "anthropic",
    "auth": {"method": "api-key", "key": API_KEY},
}


@pytest.fixture(autouse=True)
def _offline_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep validation offline: keys are valid and probes behave."""
    for name in ("_get", "_bearer_get"):
        monkeypatch.setattr(
            connection_validation, name, lambda url, key, timeout: 200
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
    def __init__(
        self, client: TestClient, conn: object, tokens: dict, url: str
    ) -> None:
        self.client = client
        self.conn = conn
        self.tokens = tokens
        self.url = url

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
    repo = tmp_path / "repo.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(repo)], check=True)
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Harness(client, conn, tokens, repo.as_uri())
    conn.close()


def _add_connection(harness: Harness) -> None:
    harness.client.post(
        "/connections", json=CONNECTION, headers=harness.auth("writer")
    )


@dataclass(frozen=True)
class Spec:
    """One collection: its route, a valid body and the field a PUT changes."""

    path: str
    body: Callable[[Harness], dict]
    change: dict = field(default_factory=dict)
    check: str = "name"
    setup: Callable[[Harness], None] = lambda harness: None


SPECS = [
    pytest.param(
        Spec("connections", lambda h: dict(CONNECTION), check="provider"),
        id="connections",
    ),
    pytest.param(
        Spec(
            "models",
            lambda h: {
                "name": "opus",
                "kind": "text",
                "connection": "anthropic-main",
                "model": "claude-opus-4-8",
                "params": {"temperature": 0.2, "max_tokens": 1024},
            },
            change={"model": "claude-sonnet-5"},
            check="model",
            setup=_add_connection,
        ),
        id="models",
    ),
    pytest.param(
        Spec(
            "prompts",
            lambda h: {
                "name": "j",
                "role": "judge",
                "template": "J {source} {summary}",
            },
            change={"template": "Score {source} vs {summary}."},
            check="template",
        ),
        id="prompts",
    ),
    pytest.param(
        Spec(
            "sources",
            lambda h: {
                "name": "webphone",
                "type": "git",
                "url": h.url,
                "auth": {"method": "none"},
            },
            check="url",
        ),
        id="sources",
    ),
]


@pytest.mark.parametrize("spec", SPECS)
def test_crud_round_trip(harness: Harness, spec: Spec) -> None:
    spec.setup(harness)
    client, base, body = harness.client, f"/{spec.path}", spec.body(harness)
    item = f"{base}/{body['name']}"

    created = client.post(base, json=body, headers=harness.auth("writer"))
    assert created.status_code == 201
    listed = client.get(base, headers=harness.auth("reader"))
    assert listed.status_code == 200
    assert [row["name"] for row in listed.json()] == [body["name"]]
    fetched = client.get(item, headers=harness.auth("reader"))
    assert fetched.status_code == 200
    assert fetched.json()[spec.check] == body[spec.check]

    replaced = {**body, **spec.change}
    put = client.put(item, json=replaced, headers=harness.auth("writer"))
    assert put.status_code == 200
    assert (
        client.get(item, headers=harness.auth("reader")).json()[spec.check]
        == replaced[spec.check]
    )

    deleted = client.delete(item, headers=harness.auth("writer"))
    assert deleted.status_code == 200
    assert client.get(item, headers=harness.auth("reader")).status_code == 404


@pytest.mark.parametrize("spec", SPECS)
def test_role_and_error_matrix(harness: Harness, spec: Spec) -> None:
    spec.setup(harness)
    client, base, body = harness.client, f"/{spec.path}", spec.body(harness)

    assert client.get(base).status_code == 401
    assert client.post(base, json=body).status_code == 401
    refused = client.post(base, json=body, headers=harness.auth("reader"))
    assert refused.status_code == 403
    assert client.get(base, headers=harness.auth("reader")).status_code == 200

    writer = harness.auth("writer")
    assert client.post(base, json=body, headers=writer).status_code == 201
    assert client.post(base, json=body, headers=writer).status_code == 409
    assert (
        client.delete(
            f"{base}/{body['name']}", headers=harness.auth("reader")
        ).status_code
        == 403
    )

    ghost = f"{base}/ghost"
    assert client.get(ghost, headers=harness.auth("reader")).status_code == 404
    assert client.delete(ghost, headers=writer).status_code == 404
