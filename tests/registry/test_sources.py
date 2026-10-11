import subprocess
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


def _bare_repo(path: Path) -> str:
    repo = path / "repo.git"
    subprocess.run(["git", "init", "--bare", "--quiet", str(repo)], check=True)
    return repo.as_uri()


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

    def body(self, **over: object) -> dict[str, object]:
        base: dict[str, object] = {
            "name": "webphone",
            "type": "git",
            "url": self.url,
            "auth": {"method": "none"},
        }
        base.update(over)
        return base


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
        yield Harness(client, conn, tokens, _bare_repo(tmp_path))
    conn.close()


def register(harness: Harness, **over: object) -> object:
    return harness.client.post(
        "/sources", json=harness.body(**over), headers=harness.auth("writer")
    )


def test_secret_is_encrypted_at_rest_and_masked(harness: Harness) -> None:
    register(harness, auth={"method": "token", "token": SECRET})
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


def test_auth_none_stores_no_key_id(harness: Harness) -> None:
    register(harness, name="open")
    row = harness.conn.execute(
        "SELECT key_id FROM registry WHERE name = 'open'"
    ).fetchone()
    assert row["key_id"] is None


def test_invalid_body_is_422(harness: Harness) -> None:
    bad = {"name": "x", "type": "git", "auth": {"method": "none"}}
    assert (
        harness.client.post(
            "/sources", json=bad, headers=harness.auth("writer")
        ).status_code
        == 422
    )


def test_unknown_type_is_422(harness: Harness) -> None:
    assert (
        harness.client.post(
            "/sources",
            json=harness.body(type="svn"),
            headers=harness.auth("writer"),
        ).status_code
        == 422
    )


def test_put_name_mismatch_is_400(harness: Harness) -> None:
    register(harness)
    assert (
        harness.client.put(
            "/sources/webphone",
            json=harness.body(name="other"),
            headers=harness.auth("writer"),
        ).status_code
        == 400
    )


def test_unreachable_source_is_rejected_400(harness: Harness) -> None:
    missing = (Path(harness.url[len("file://") :]).parent / "nope.git").as_uri()
    response = harness.client.post(
        "/sources",
        json=harness.body(url=missing),
        headers=harness.auth("writer"),
    )
    assert response.status_code == 400
    assert (
        harness.client.get(
            "/sources/webphone", headers=harness.auth("reader")
        ).status_code
        == 404
    )
