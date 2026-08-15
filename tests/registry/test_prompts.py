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
ROLES = ("condense", "brief", "brief-upper", "judge")


def prompt(role: str = "condense", **over: object) -> dict[str, object]:
    body: dict[str, object] = {
        "name": role,
        "role": role,
        "template": "Summarize {section} in {n} words.",
    }
    body.update(over)
    return body


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
        "/prompts", json=body, headers=harness.auth(role)
    )


@pytest.mark.parametrize("role", ROLES)
def test_registers_each_valid_role(harness: Harness, role: str) -> None:
    assert post(harness, prompt(role)).status_code == 201
    fetched = harness.client.get(
        f"/prompts/{role}", headers=harness.auth("reader")
    )
    assert fetched.status_code == 200
    got = fetched.json()
    assert got["role"] == role
    assert got["template"] == "Summarize {section} in {n} words."


def test_bad_role_is_422(harness: Harness) -> None:
    assert post(harness, prompt(role="rewrite")).status_code == 422


def test_crud_round_trip(harness: Harness) -> None:
    post(harness, prompt("judge", name="j"))
    replaced = prompt("judge", name="j", template="Score {a} vs {b}.")
    assert (
        harness.client.put(
            "/prompts/j", json=replaced, headers=harness.auth("writer")
        ).status_code
        == 200
    )
    assert (
        harness.client.get("/prompts/j", headers=harness.auth("reader")).json()[
            "template"
        ]
        == "Score {a} vs {b}."
    )
    assert (
        harness.client.delete(
            "/prompts/j", headers=harness.auth("writer")
        ).status_code
        == 200
    )


def test_secretless_stores_null_key_id(harness: Harness) -> None:
    post(harness, prompt("brief", name="b"))
    row = harness.conn.execute(
        "SELECT key_id FROM registry "
        "WHERE collection = 'prompts' AND name = 'b'"
    ).fetchone()
    assert row["key_id"] is None


def test_role_and_error_matrix(harness: Harness) -> None:
    assert harness.client.get("/prompts").status_code == 401
    assert post(harness, prompt(), role="reader").status_code == 403
    assert (
        harness.client.get(
            "/prompts", headers=harness.auth("reader")
        ).status_code
        == 200
    )
    assert post(harness, prompt()).status_code == 201
    assert post(harness, prompt()).status_code == 409
    assert (
        harness.client.get(
            "/prompts/ghost", headers=harness.auth("reader")
        ).status_code
        == 404
    )
