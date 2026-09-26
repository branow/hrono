"""#174 (T57.3): watching a job's progress live.

The fan-out watched here is created through `POST /jobs`, not planted (#176),
so these tests fail if the producer breaks as well as if the stream does.
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
from hrono.jobs import store
from hrono.server import events
from hrono.server.app import create_app
from tests.jobs.test_cancel import registry_insert

KEY = Fernet.generate_key()


class Harness:
    def __init__(self, client: TestClient, token: str, conn: object) -> None:
        self.client = client
        self.headers = {"Authorization": f"Bearer {token}"}
        self.conn = conn

    def fan_out(self) -> str:
        response = self.client.post(
            "/jobs",
            json={"op": "sync", "scope": {"type": "all"}},
            headers=self.headers,
        )
        return str(response.json()["job_id"])

    def watch(self, job_id: str) -> list[dict]:
        """Read the whole stream to its close and return the states."""
        with self.client.stream(
            "GET", f"/jobs/{job_id}/events", headers=self.headers
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            return [
                json.loads(line[len("data: ") :])
                for line in response.iter_lines()
                if line.startswith("data: ")
            ]


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    for name in ("alpha-src", "beta-src"):
        registry_insert(conn, name)
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        yield Harness(client, token, conn)
    conn.close()


def test_a_finished_job_gets_its_state_and_a_closed_stream(
    harness: Harness,
) -> None:
    # not a hang: `hrono jobs watch` on a job that finished while you were
    # typing has to return, or it is unusable in a script.
    parent = harness.fan_out()
    for child in store.children(harness.conn, parent):  # type: ignore[arg-type]
        store.set_status(harness.conn, child["id"], "succeeded", None, "t")  # type: ignore[arg-type]

    states = harness.watch(parent)

    assert states == [
        {
            "id": parent,
            "status": "succeeded",
            "progress": {"done": 2, "total": 2},
        }
    ]


def test_the_stream_follows_a_job_to_its_end(harness: Harness) -> None:
    """The live case: states arrive as they change, then the stream ends.

    The job is advanced from another thread WHILE the stream is open, which is
    the only way to prove it is following rather than reporting once.
    """
    import threading
    import time

    parent = harness.fan_out()
    children = [
        str(row["id"])
        for row in store.children(harness.conn, parent)  # type: ignore[arg-type]
    ]

    def advance() -> None:
        for child in children:
            time.sleep(events.POLL_SECONDS * 1.5)
            store.set_status(harness.conn, child, "succeeded", None, "t")  # type: ignore[arg-type]

    mover = threading.Thread(target=advance, daemon=True)
    mover.start()
    states = harness.watch(parent)
    mover.join(timeout=10)

    assert [state["status"] for state in states] == [
        "pending",
        "partial",
        "succeeded",
    ]
    assert [state["progress"]["done"] for state in states] == [0, 1, 2]


def test_an_unknown_job_is_a_404_before_any_stream(harness: Harness) -> None:
    # an empty `text/event-stream` looks like a job with nothing to say
    response = harness.client.get(
        "/jobs/job_nope/events", headers=harness.headers
    )

    assert response.status_code == 404
    assert "text/event-stream" not in response.headers.get("content-type", "")


def test_a_cancelled_job_ends_the_stream(harness: Harness) -> None:
    parent = harness.fan_out()
    harness.client.post(f"/jobs/{parent}/cancel", headers=harness.headers)

    states = harness.watch(parent)

    assert states[-1]["status"] == "canceled"


def test_the_frame_is_a_named_sse_event() -> None:
    # `event: state` lets a browser `EventSource` addEventListener rather than
    # parse every message to find out what it is.
    text = events.frame({"id": "job_1", "status": "running"})

    assert text.startswith("event: state\ndata: ")
    assert text.endswith("\n\n")
    assert json.loads(text.split("data: ", 1)[1]) == {
        "id": "job_1",
        "status": "running",
    }


def test_the_stream_waits_for_a_running_stage_after_a_failure(
    harness: Harness,
) -> None:
    """Found by driving it: the stream ended at `failed 1/2`.

    A parent's status goes terminal the moment one child fails — correct for a
    GET, wrong for a watch, because the other stage is still writing and a
    watcher who acts on that acts on a database still being changed.
    """
    parent = harness.fan_out()
    children = [
        str(row["id"])
        for row in store.children(harness.conn, parent)  # type: ignore[arg-type]
    ]
    store.set_status(harness.conn, children[0], "failed", "boom", "t")  # type: ignore[arg-type]
    store.claim_next(harness.conn, "t")  # type: ignore[arg-type]  # the other is running

    state = events.state_of(harness.conn, parent)  # type: ignore[arg-type]

    assert state is not None
    assert state["status"] == "failed"  # the outcome IS decided
    assert events.is_terminal(state) is False  # and the watch stays open

    store.set_status(harness.conn, children[1], "failed", "boom", "t")  # type: ignore[arg-type]
    finished = events.state_of(harness.conn, parent)  # type: ignore[arg-type]
    assert finished is not None
    assert events.is_terminal(finished) is True


def test_a_leaf_ends_on_its_own_status(harness: Harness) -> None:
    # no progress to wait on: its status is the whole story.
    assert events.is_terminal({"id": "x", "status": "succeeded"}) is True
    assert events.is_terminal({"id": "x", "status": "running"}) is False
