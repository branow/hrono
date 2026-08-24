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


class Harness:
    def __init__(self, client: TestClient, tokens: dict[str, str]) -> None:
        self.client = client
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
        yield Harness(client, tokens)
    conn.close()


def test_maintain_requires_auth(harness: Harness) -> None:
    assert harness.client.post("/trees/default/maintain").status_code == 401


def test_reader_cannot_maintain(harness: Harness) -> None:
    resp = harness.client.post(
        "/trees/default/maintain", headers=harness.auth("reader")
    )
    assert resp.status_code == 403


def test_writer_kicks_a_maintain_job_and_gets_a_job_id(
    harness: Harness,
) -> None:
    resp = harness.client.post(
        "/trees/default/maintain", headers=harness.auth("writer")
    )
    assert resp.status_code == 200
    job_id = resp.json()["job_id"]
    assert job_id
    # the job is real and trackable via the jobs route, scoped to the tree
    fetched = harness.client.get(
        f"/jobs/{job_id}", headers=harness.auth("reader")
    ).json()
    assert fetched["op"] == "maintain"
    assert fetched["tree"] == "default"
