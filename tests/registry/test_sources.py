from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.server.app import create_app

KEY = Fernet.generate_key()
SECRET = "gh-token-supersecret"
GIT = {
    "name": "webphone",
    "type": "git",
    "url": "https://github.com/acme/webphone",
    "auth": {"method": "token", "token": SECRET},
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


def register(harness: Harness, body: dict | None = None) -> object:
    return harness.client.post(
        "/sources", json=body or GIT, headers=harness.auth("writer")
    )


def test_register_list_fetch(harness: Harness) -> None:
    assert register(harness).status_code == 201
    listed = harness.client.get("/sources", headers=harness.auth("reader"))
    assert listed.status_code == 200
    assert [s["name"] for s in listed.json()] == ["webphone"]
    fetched = harness.client.get(
        "/sources/webphone", headers=harness.auth("reader")
    )
    assert fetched.status_code == 200
    assert fetched.json()["url"] == GIT["url"]


def test_put_replaces(harness: Harness) -> None:
    register(harness)
    changed = {**GIT, "url": "https://github.com/acme/renamed"}
    put = harness.client.put(
        "/sources/webphone", json=changed, headers=harness.auth("writer")
    )
    assert put.status_code == 200
    fetched = harness.client.get(
        "/sources/webphone", headers=harness.auth("reader")
    )
    assert fetched.json()["url"] == "https://github.com/acme/renamed"


def test_delete_removes(harness: Harness) -> None:
    register(harness)
    assert (
        harness.client.delete(
            "/sources/webphone", headers=harness.auth("writer")
        ).status_code
        == 200
    )
    assert (
        harness.client.get(
            "/sources/webphone", headers=harness.auth("reader")
        ).status_code
        == 404
    )


def test_unauthenticated_is_401(harness: Harness) -> None:
    assert harness.client.get("/sources").status_code == 401
    assert harness.client.post("/sources", json=GIT).status_code == 401


def test_reader_may_read_not_write(harness: Harness) -> None:
    register(harness)
    assert (
        harness.client.get(
            "/sources", headers=harness.auth("reader")
        ).status_code
        == 200
    )
    assert (
        harness.client.post(
            "/sources",
            json={**GIT, "name": "two"},
            headers=harness.auth("reader"),
        ).status_code
        == 403
    )
    assert (
        harness.client.put(
            "/sources/webphone", json=GIT, headers=harness.auth("reader")
        ).status_code
        == 403
    )
    assert (
        harness.client.delete(
            "/sources/webphone", headers=harness.auth("reader")
        ).status_code
        == 403
    )


def test_secret_is_encrypted_at_rest_and_masked(harness: Harness) -> None:
    register(harness)
    fetched = harness.client.get(
        "/sources/webphone", headers=harness.auth("reader")
    )
    assert fetched.json()["auth"]["token"] == "***"
    assert SECRET not in fetched.text

    row = harness.conn.execute(
        "SELECT config, key_id FROM registry "
        "WHERE collection = 'sources' AND name = 'webphone'"
    ).fetchone()
    assert SECRET not in row["config"]
    assert row["key_id"] == 1


def test_post_response_masks_the_secret(harness: Harness) -> None:
    created = register(harness)
    assert created.json()["auth"]["token"] == "***"


def test_auth_none_stores_no_key_id(harness: Harness) -> None:
    register(harness, {**GIT, "name": "open", "auth": {"method": "none"}})
    row = harness.conn.execute(
        "SELECT key_id FROM registry WHERE name = 'open'"
    ).fetchone()
    assert row["key_id"] is None


def test_duplicate_is_409(harness: Harness) -> None:
    register(harness)
    assert register(harness).status_code == 409


def test_invalid_body_is_422(harness: Harness) -> None:
    bad = {"name": "x", "type": "git", "auth": {"method": "none"}}
    assert (
        harness.client.post(
            "/sources", json=bad, headers=harness.auth("writer")
        ).status_code
        == 422
    )


def test_unknown_type_is_422(harness: Harness) -> None:
    bad = {**GIT, "type": "svn"}
    assert (
        harness.client.post(
            "/sources", json=bad, headers=harness.auth("writer")
        ).status_code
        == 422
    )


def test_put_name_mismatch_is_400(harness: Harness) -> None:
    register(harness)
    mismatched = {**GIT, "name": "other"}
    assert (
        harness.client.put(
            "/sources/webphone", json=mismatched, headers=harness.auth("writer")
        ).status_code
        == 400
    )


def test_unknown_name_is_404(harness: Harness) -> None:
    assert (
        harness.client.get(
            "/sources/ghost", headers=harness.auth("reader")
        ).status_code
        == 404
    )
    assert (
        harness.client.put(
            "/sources/ghost",
            json={**GIT, "name": "ghost"},
            headers=harness.auth("writer"),
        ).status_code
        == 404
    )
    assert (
        harness.client.delete(
            "/sources/ghost", headers=harness.auth("writer")
        ).status_code
        == 404
    )
