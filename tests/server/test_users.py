from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.db.database import open_database
from hrono.server.app import create_app

KEY = Fernet.generate_key()


class Harness:
    def __init__(self, client: TestClient, tokens: dict[str, str]) -> None:
        self.client = client
        self.tokens = tokens

    def auth(self, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[role]}"}


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    conn = open_database(tmp_path / "hrono.db")
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Harness(client, tokens)
    conn.close()


def test_health_and_version_need_no_token(harness: Harness) -> None:
    assert harness.client.get("/health").status_code == 200
    assert harness.client.get("/version").status_code == 200


def test_missing_header_is_401(harness: Harness) -> None:
    response = harness.client.get("/users")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"
    assert response.json()["error"]["code"] == "unauthorized"


def test_malformed_header_is_401(harness: Harness) -> None:
    assert (
        harness.client.get(
            "/users", headers={"Authorization": "Basic abc"}
        ).status_code
        == 401
    )
    assert (
        harness.client.get(
            "/users", headers={"Authorization": "Bearer "}
        ).status_code
        == 401
    )


def test_unknown_token_is_401(harness: Harness) -> None:
    response = harness.client.get(
        "/users", headers={"Authorization": "Bearer nope"}
    )
    assert response.status_code == 401


def test_reader_may_list_users(harness: Harness) -> None:
    response = harness.client.get("/users", headers=harness.auth("reader"))
    assert response.status_code == 200
    names = {u["name"] for u in response.json()}
    assert names == {"reader", "writer", "admin"}


def test_list_users_never_exposes_token_or_hash(harness: Harness) -> None:
    response = harness.client.get("/users", headers=harness.auth("reader"))
    body = response.text
    for token in harness.tokens.values():
        assert token not in body
    for user in response.json():
        assert set(user) == {"name", "role", "created_at"}


def test_reader_cannot_create_or_delete(harness: Harness) -> None:
    created = harness.client.post(
        "/users",
        json={"name": "x", "role": "reader"},
        headers=harness.auth("reader"),
    )
    assert created.status_code == 403
    deleted = harness.client.delete(
        "/users/writer", headers=harness.auth("reader")
    )
    assert deleted.status_code == 403


def test_writer_cannot_create_but_satisfies_reader(harness: Harness) -> None:
    assert (
        harness.client.get("/users", headers=harness.auth("writer")).status_code
        == 200
    )
    assert (
        harness.client.post(
            "/users",
            json={"name": "x", "role": "reader"},
            headers=harness.auth("writer"),
        ).status_code
        == 403
    )


def test_admin_creates_user_and_gets_token_once(harness: Harness) -> None:
    response = harness.client.post(
        "/users",
        json={"name": "newbie", "role": "writer"},
        headers=harness.auth("admin"),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "newbie"
    assert body["role"] == "writer"
    assert body["token"]

    listed = harness.client.get("/users", headers=harness.auth("admin"))
    assert body["token"] not in listed.text


def test_admin_can_delete_user(harness: Harness) -> None:
    assert (
        harness.client.delete(
            "/users/reader", headers=harness.auth("admin")
        ).status_code
        == 200
    )
    remaining = harness.client.get("/users", headers=harness.auth("admin"))
    assert {u["name"] for u in remaining.json()} == {"writer", "admin"}


def test_duplicate_name_is_409(harness: Harness) -> None:
    response = harness.client.post(
        "/users",
        json={"name": "admin", "role": "reader"},
        headers=harness.auth("admin"),
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_invalid_role_is_422(harness: Harness) -> None:
    response = harness.client.post(
        "/users",
        json={"name": "weird", "role": "superuser"},
        headers=harness.auth("admin"),
    )
    assert response.status_code == 422


def test_delete_unknown_is_404(harness: Harness) -> None:
    response = harness.client.delete(
        "/users/ghost", headers=harness.auth("admin")
    )
    assert response.status_code == 404


def test_admin_satisfies_reader_and_writer_routes(harness: Harness) -> None:
    assert (
        harness.client.get("/users", headers=harness.auth("admin")).status_code
        == 200
    )
    assert (
        harness.client.post(
            "/users",
            json={"name": "created-by-admin", "role": "reader"},
            headers=harness.auth("admin"),
        ).status_code
        == 201
    )
