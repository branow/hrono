"""Stopping a run that is already going.

Every test here reaches the cancel through the API, and the fan-out it cancels
is created through the API too — `POST /jobs` with a scope over many sources.
Planting the parent with `store.create_fanout` would prove the canceller and
say nothing about whether an operator can reach any of it.
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
from hrono.server.app import create_app

KEY = Fernet.generate_key()


class Harness:
    def __init__(self, client: TestClient, tokens: dict, conn: object) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn

    def auth(self, role: str) -> dict:
        return {"Authorization": f"Bearer {self.tokens[role]}"}

    def fan_out(self) -> str:
        response = self.client.post(
            "/jobs",
            json={"op": "sync", "scope": {"type": "all"}},
            headers=self.auth("admin"),
        )
        assert response.status_code == 201
        return str(response.json()["job_id"])

    def cancel(self, job_id: str, role: str = "admin") -> object:
        return self.client.post(
            f"/jobs/{job_id}/cancel", headers=self.auth(role)
        )

    def statuses(self, parent: str) -> list[str]:
        return [
            str(child["status"])
            for child in self.client.get(
                f"/jobs/{parent}/children", headers=self.auth("admin")
            ).json()
        ]

    def status_of(self, job_id: str) -> str:
        return str(
            self.client.get(
                f"/jobs/{job_id}", headers=self.auth("admin")
            ).json()["status"]
        )


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    for name in ("alpha-src", "beta-src", "gamma-src"):
        registry_insert(conn, name)
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        yield Harness(client, tokens, conn)
    conn.close()


def registry_insert(conn: object, name: str) -> None:
    from hrono.registry import store as registry_store

    registry_store.insert(  # type: ignore[arg-type]
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


def test_cancelling_a_parent_stops_its_pending_children(
    harness: Harness,
) -> None:
    parent = harness.fan_out()

    response = harness.cancel(parent)

    assert response.status_code == 200  # type: ignore[attr-defined]
    assert response.json() == {  # type: ignore[attr-defined]
        "job_id": parent,
        "stopped": 3,
        "running": 0,
        "finished": 0,
    }
    assert harness.statuses(parent) == ["canceled"] * 3


def test_the_parent_then_reads_as_canceled(harness: Harness) -> None:
    # the derived answer and the stored row AGREE: once the last
    # child is terminal the parent is finalized, because a parent left
    # 'pending' forever sat in the claim scan and the status filters for the
    # life of the database.
    parent = harness.fan_out()

    harness.cancel(parent)

    assert harness.status_of(parent) == "canceled"
    stored = store.get(harness.conn, parent)  # type: ignore[arg-type]
    assert stored is not None
    assert stored["status"] == "canceled"  # finalized, not derived-only


def test_a_running_child_is_signaled_and_reported(
    harness: Harness,
) -> None:
    """The honest half: a handler cannot be interrupted mid-transaction.

    A thread inside a SQLite transaction cannot be killed safely — but the ROW
    flips to canceled, which is the stop signal ``pool.running`` polls between
    calls, and ``running: 1`` in the response means "told to stop, finishing
    its step". The worker's terminal write is guarded on status = 'running', so
    the signal is never overwritten by the step's outcome.
    """
    parent = harness.fan_out()
    claimed = store.claim_next(harness.conn, "t")  # type: ignore[arg-type]
    assert claimed is not None

    response = harness.cancel(parent)

    assert response.json() == {  # type: ignore[attr-defined]
        "job_id": parent,
        "stopped": 2,
        "running": 1,
        "finished": 0,
    }
    assert sorted(harness.statuses(parent)) == ["canceled"] * 3
    # and the signal sticks: a worker announcing the step's outcome now
    # cannot overwrite the cancel.
    store.set_status(
        harness.conn,  # type: ignore[arg-type]
        claimed["id"],
        "succeeded",
        None,
        "t2",
        expected="running",
    )
    row = store.get(harness.conn, claimed["id"])  # type: ignore[arg-type]
    assert row is not None and row["status"] == "canceled"


def test_a_finished_child_keeps_its_outcome(harness: Harness) -> None:
    # cancel is not an undo.
    parent = harness.fan_out()
    children = [
        str(child["id"])
        for child in harness.client.get(
            f"/jobs/{parent}/children", headers=harness.auth("admin")
        ).json()
    ]
    store.set_status(harness.conn, children[0], "succeeded", None, "t")  # type: ignore[arg-type]

    response = harness.cancel(parent)

    assert response.json()["finished"] == 1  # type: ignore[index]
    assert harness.statuses(parent).count("succeeded") == 1


def test_cancelling_a_standalone_job_stops_it(harness: Harness) -> None:
    response = harness.client.post(
        "/jobs",
        json={"op": "monitor", "scope": {}},
        headers=harness.auth("admin"),
    )
    job_id = response.json()["job_id"]

    assert harness.cancel(job_id).json()["stopped"] == 1  # type: ignore[attr-defined]
    assert harness.status_of(job_id) == "canceled"


def test_cancelling_one_run_leaves_another_alone(harness: Harness) -> None:
    # a fixture with ONE parent cannot show this: cancelling everything
    # pending and cancelling the target's own children look identical when
    # there is nothing else in the queue.
    mine = harness.fan_out()
    theirs = harness.fan_out()

    harness.cancel(mine)

    assert harness.statuses(mine) == ["canceled"] * 3
    assert harness.statuses(theirs) == ["pending"] * 3


def test_cancel_is_admin_only(harness: Harness) -> None:
    parent = harness.fan_out()

    assert harness.cancel(parent, "writer").status_code == 403  # type: ignore[attr-defined]
    assert harness.statuses(parent) == ["pending"] * 3


def test_cancelling_an_unknown_job_is_a_404(harness: Harness) -> None:
    assert harness.cancel("job_nope").status_code == 404  # type: ignore[attr-defined]


def test_the_cli_says_what_it_could_not_stop(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from hrono import cli

    parent = harness.fan_out()
    store.claim_next(harness.conn, "t")  # type: ignore[arg-type]

    class Wired:
        def post(self, path: str, body: dict, **_: object) -> object:
            return harness.client.post(
                path, json=body, headers=harness.auth("admin")
            ).json()

    monkeypatch.setattr("hrono.jobs.commands.from_profile", lambda: Wired())
    result = CliRunner().invoke(cli.app, ["jobs", "cancel", parent])

    assert result.exit_code == 0
    assert "Stopped 2 pending jobs." in result.output
    assert "1 stage was told to stop and will finish its step." in result.output
