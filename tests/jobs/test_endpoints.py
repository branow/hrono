from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.jobs import store
from hrono.server.app import create_app

KEY = Fernet.generate_key()


class Harness:
    def __init__(self, client: TestClient, tokens: dict) -> None:
        self.client = client
        self.tokens = tokens

    def auth(self, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[role]}"}


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1] for role in ("reader", "admin")
    }
    store.insert(conn, "job_a", None, None, "sync", '{"type":"all"}', "t")
    store.set_status(conn, "job_a", "succeeded", None, "t")
    store.insert(conn, "job_b", None, None, "split", '{"type":"all"}', "t")
    store.set_status(conn, "job_b", "failed", "boom", "t")
    store.insert(conn, "job_c", None, None, "propagate", '{"type":"all"}', "t")
    store.set_status(
        conn,
        "job_c",
        "succeeded",
        None,
        "t",
        '{"judged": 0, "incomplete": true}',
    )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Harness(client, tokens)
    conn.close()


def test_unauthenticated_is_401(harness: Harness) -> None:
    assert harness.client.get("/jobs").status_code == 401


def test_reader_lists_jobs(harness: Harness) -> None:
    response = harness.client.get("/jobs", headers=harness.auth("reader"))
    assert response.status_code == 200
    assert {j["id"] for j in response.json()} == {"job_a", "job_b", "job_c"}


def test_list_filters_by_status(harness: Harness) -> None:
    response = harness.client.get(
        "/jobs?status=failed", headers=harness.auth("reader")
    )
    assert [j["id"] for j in response.json()] == ["job_b"]


def test_fetch_one_job(harness: Harness) -> None:
    response = harness.client.get("/jobs/job_b", headers=harness.auth("reader"))
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "failed"
    assert body["error"] == "boom"
    assert body["scope"] == {"type": "all"}


def test_unknown_job_is_404(harness: Harness) -> None:
    assert (
        harness.client.get(
            "/jobs/ghost", headers=harness.auth("reader")
        ).status_code
        == 404
    )


def test_the_job_read_path_carries_the_ops_outcome(harness: Harness) -> None:
    # #132: the operator surface that exists today. A run that declined part of
    # its work has to be visible HERE, not only in a table nothing selects.
    response = harness.client.get("/jobs/job_c", headers=harness.auth("reader"))

    assert response.status_code == 200
    assert response.json()["result"] == {"judged": 0, "incomplete": True}


def test_a_job_with_nothing_to_report_carries_no_result(
    harness: Harness,
) -> None:
    response = harness.client.get("/jobs/job_a", headers=harness.auth("reader"))

    assert response.status_code == 200
    assert response.json()["result"] is None
