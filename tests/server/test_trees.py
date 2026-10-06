import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster.incubator import park
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from hrono.registry import store as registry_store
from hrono.server.app import create_app

KEY = Fernet.generate_key()


class Harness:
    def __init__(
        self,
        client: TestClient,
        tokens: dict[str, str],
        conn: sqlite3.Connection,
    ) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn

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
        yield Harness(client, tokens, conn)
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


def test_maintain_for_an_unregistered_tree_is_refused_and_queues_nothing(
    harness: Harness,
) -> None:
    resp = harness.client.post(
        "/trees/nope/maintain", headers=harness.auth("writer")
    )

    assert resp.status_code == 404
    assert "tree not registered: nope" in resp.json()["error"]["message"]
    assert harness.conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 0
    assert harness.conn.execute("SELECT COUNT(*) FROM nodes").fetchone()[0] == 0


def test_maintain_for_a_registered_tree_queues_a_job(
    harness: Harness,
) -> None:
    registry_store.insert(
        harness.conn,
        "trees",
        "alpha",
        json.dumps({"name": "alpha"}),
        None,
        "t",
    )
    harness.conn.commit()

    resp = harness.client.post(
        "/trees/alpha/maintain", headers=harness.auth("writer")
    )

    assert resp.status_code == 200
    row = harness.conn.execute(
        "SELECT id FROM jobs WHERE tree = 'alpha'"
    ).fetchone()
    assert row["id"] == resp.json()["job_id"]


def test_pending_requires_auth(harness: Harness) -> None:
    assert harness.client.get("/trees/default/pending").status_code == 401


def test_reader_sees_an_empty_pool(harness: Harness) -> None:
    resp = harness.client.get(
        "/trees/default/pending", headers=harness.auth("reader")
    )
    assert resp.status_code == 200
    assert resp.json() == {"count": 0, "pending": []}


def test_a_parked_chunk_is_visible_through_the_pool_route(
    harness: Harness,
) -> None:
    with harness.conn:
        digest = content_hash(b"stranded\n")
        upsert_content(harness.conn, digest, b"stranded\n")
        section_id = insert_section(
            harness.conn,
            source="repo",
            address=Address("git", "ex/repo", "docs/stranded.md", "v1"),
            start=0,
            end=9,
            content_hash=digest,
            ordinal=0,
        )
        park(harness.conn, "default", section_id, batch=3)
    body = harness.client.get(
        "/trees/default/pending", headers=harness.auth("reader")
    ).json()
    assert body["count"] == 1
    assert body["pending"] == [
        {
            "section_id": section_id,
            "content_hash": digest,
            "path": "docs/stranded.md",
            "batch": 3,
        }
    ]


def test_a_repeated_kick_hands_back_the_job_already_queued(
    harness: Harness,
) -> None:
    # a double-clicked button queued the same multi-minute, LLM-billed build
    # twice; one live job per (op, tree) is the useful maximum, and answering
    # with its id makes the retry idempotent instead of an error.
    # The worker is stopped first (the #194 harness rule): with it running,
    # the first job can reach a terminal state between the two POSTs and the
    # dedupe correctly stops applying.
    worker = harness.client.app.state.worker  # type: ignore[attr-defined]
    worker.stop()
    worker.join(timeout=5)
    first = harness.client.post(
        "/trees/default/maintain", headers=harness.auth("writer")
    ).json()["job_id"]
    second = harness.client.post(
        "/trees/default/maintain", headers=harness.auth("writer")
    ).json()["job_id"]

    assert second == first

    synced = harness.client.post(
        "/trees/default/sync", headers=harness.auth("writer")
    ).json()["job_id"]
    again = harness.client.post(
        "/trees/default/sync", headers=harness.auth("writer")
    ).json()["job_id"]
    assert again == synced
    assert synced != first  # per op: a sync is not the queued maintain


def test_sync_for_an_unregistered_tree_is_refused_and_queues_nothing(
    harness: Harness,
) -> None:
    # `maintain` checked; `sync` forgot to, so unregistered trees could be
    # queued for the incremental chain.
    resp = harness.client.post(
        "/trees/nobody/sync", headers=harness.auth("writer")
    )
    assert resp.status_code == 404
