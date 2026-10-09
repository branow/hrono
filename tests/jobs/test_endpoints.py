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
    # a job's failure is served in the same envelope as an HTTP error
    assert body["error"] == {
        "code": "internal-error",
        "message": "boom",
        "details": None,
    }
    assert body["scope"] == {"type": "all"}


def test_unknown_job_is_404(harness: Harness) -> None:
    assert (
        harness.client.get(
            "/jobs/ghost", headers=harness.auth("reader")
        ).status_code
        == 404
    )


def test_the_job_read_path_carries_the_ops_outcome(harness: Harness) -> None:
    # the operator surface. A run that declined part of
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


def test_an_admin_can_run_any_registered_op(harness: Harness) -> None:
    # the service door: without it an operator inserts job rows into SQLite
    # by hand to find out why a tree is stuck.
    response = harness.client.post(
        "/jobs",
        json={"op": "monitor", "scope": {}, "tree": "default"},
        headers=harness.auth("admin"),
    )

    assert response.status_code == 201
    assert response.json()["job_id"]


def test_a_writer_cannot_open_the_service_door(harness: Harness) -> None:
    # admin, not writer: this runs an expensive or destructive stage out of
    # sequence, and the role should say so.
    response = harness.client.post(
        "/jobs",
        json={"op": "monitor", "scope": {}},
        headers=harness.auth("reader"),
    )

    assert response.status_code == 403


def test_an_unknown_op_is_refused_at_the_boundary(harness: Harness) -> None:
    # a typo must be a clear 4xx here, not a job that fails in a worker minutes
    # later with nobody watching.
    response = harness.client.post(
        "/jobs",
        json={"op": "propogate", "scope": {}},
        headers=harness.auth("admin"),
    )

    assert response.status_code == 400
    body = response.json()
    assert body["error"]["code"]
    assert "propagate" in body["error"]["details"]["registered"]
