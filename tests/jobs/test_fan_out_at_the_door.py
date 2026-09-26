"""#175: a source-scoped op over every source really does fan out.

`fan_out` was called from TESTS ONLY — the machinery existed, its own tests
passed, and no request could reach it. So these tests go through the API and
read the parent back; none of them calls `fan_out` itself, because doing that
is how nobody noticed.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.jobs.scope import SOURCE_SCOPED, fans_out
from hrono.registry import store as registry_store
from hrono.server.app import create_app

KEY = Fernet.generate_key()


class Harness:
    def __init__(self, client: TestClient, token: str) -> None:
        self.client = client
        self.headers = {"Authorization": f"Bearer {token}"}

    def run(self, body: dict) -> str:
        response = self.client.post("/jobs", json=body, headers=self.headers)
        assert response.status_code == 201, response.json()
        return str(response.json()["job_id"])

    def children(self, job_id: str) -> list[dict]:
        return self.client.get(
            f"/jobs/{job_id}/children", headers=self.headers
        ).json()

    def job(self, job_id: str) -> dict:
        return self.client.get(f"/jobs/{job_id}", headers=self.headers).json()


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    for name in ("alpha-src", "beta-src", "gamma-src"):
        registry_store.insert(
            conn,
            "sources",
            name,
            json.dumps(
                {
                    "name": name,
                    "type": "git",
                    "url": f"https://ex/{name}.git",
                    "auth": None,
                }
            ),
            None,
            "t",
        )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        yield Harness(client, token)
    conn.close()


def test_a_source_scoped_op_over_all_sources_fans_out(
    harness: Harness,
) -> None:
    job_id = harness.run({"op": "sync", "scope": {"type": "all"}})

    children = harness.children(job_id)

    assert len(children) == 3
    assert {child["scope"]["name"] for child in children} == {
        "alpha-src",
        "beta-src",
        "gamma-src",
    }
    assert all(child["parent_id"] == job_id for child in children)


def test_the_parent_answers_for_them(harness: Harness) -> None:
    # the point of fanning out: #172's aggregation now has something to
    # aggregate, which it did not before this ticket.
    job_id = harness.run({"op": "sync", "scope": {"type": "all"}})

    answer = harness.job(job_id)

    assert answer["progress"] == {"done": 0, "total": 3}
    assert answer["status"] == "pending"


def test_an_explicit_single_source_stays_one_job(harness: Harness) -> None:
    # a parent with one child is a layer the operator clicks through to reach
    # the thing they asked for.
    job_id = harness.run(
        {"op": "sync", "scope": {"type": "source", "name": "alpha-src"}}
    )

    assert harness.children(job_id) == []
    assert "progress" not in harness.job(job_id)


def test_an_op_that_takes_the_whole_tree_does_not_fan_out(
    harness: Harness,
) -> None:
    # `monitor` reads no source name; one job per source would hand it a scope
    # it cannot read, three times.
    job_id = harness.run({"op": "monitor", "scope": {}})

    assert harness.children(job_id) == []


@pytest.mark.parametrize(
    ("op", "scope", "expected"),
    [
        ("sync", {"type": "all"}, True),
        ("split", {}, True),  # an omitted scope means everything
        ("sync", {"type": "source", "name": "x"}, False),
        ("monitor", {"type": "all"}, False),
        ("embed", {}, False),
    ],
)
def test_which_requests_fan_out(op: str, scope: dict, expected: bool) -> None:
    assert fans_out(op, scope) is expected


def test_the_source_scoped_ops_are_the_ones_that_read_a_source() -> None:
    """The set is data, and this is the reason it holds those two names.

    `sync` and `split` both do `job.scope["name"]` and can do nothing without
    it. If a third op ever reads a source name, it belongs here — and if one of
    these stops, it does not.
    """
    assert {"sync", "split"} == SOURCE_SCOPED
