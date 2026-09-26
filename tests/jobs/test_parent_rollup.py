"""#172 (T57.1): the parent's answer, over HTTP.

`tests/jobs/test_aggregate.py` states the rules as a table; this proves the
route asks for them, and that a LEAF's answer is unchanged.
"""

from __future__ import annotations

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
SCOPE = '{"type":"all"}'


class Harness:
    def __init__(self, client: TestClient, token: str, conn: object) -> None:
        self.client = client
        self.headers = {"Authorization": f"Bearer {token}"}
        self.conn = conn

    def get(self, path: str) -> dict:
        return self.client.get(path, headers=self.headers).json()


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    """A server whose WORKER is stopped, then jobs planted in known states.

    The worker claims pending leaves and runs them, so a fixture that plants
    `pending` children in a live server is racing it — mine did, and the
    children came back `failed` from a `maintain` that had no sources. This is
    the READ surface; the worker has its own tests.
    """
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        store.create_fanout(
            conn,
            "job_parent",
            "maintain",
            SCOPE,
            [("job_one", SCOPE), ("job_two", SCOPE), ("job_three", SCOPE)],
            "default",
            "t",
        )
        store.insert(conn, "job_alone", None, None, "embed", SCOPE, "t")
        yield Harness(client, token, conn)
    conn.close()


def _finish(h: Harness, job_id: str, status: str) -> None:
    store.set_status(h.conn, job_id, status, None, "t")  # type: ignore[arg-type]


def test_a_parent_mid_run_reports_partial_and_its_progress(
    harness: Harness,
) -> None:
    _finish(harness, "job_one", "succeeded")

    answer = harness.get("/jobs/job_parent")

    assert answer["status"] == "partial"
    assert answer["progress"] == {"done": 1, "total": 3}


def test_a_parent_whose_children_all_succeeded_succeeds(
    harness: Harness,
) -> None:
    for job_id in ("job_one", "job_two", "job_three"):
        _finish(harness, job_id, "succeeded")

    answer = harness.get("/jobs/job_parent")

    assert answer["status"] == "succeeded"
    assert answer["progress"] == {"done": 3, "total": 3}


def test_one_failed_child_fails_the_parent(harness: Harness) -> None:
    _finish(harness, "job_one", "succeeded")
    _finish(harness, "job_two", "failed")

    assert harness.get("/jobs/job_parent")["status"] == "failed"


def test_the_parents_own_stored_row_is_not_what_is_reported(
    harness: Harness,
) -> None:
    """The point of deriving it: the stored row goes stale and is ignored.

    `create_fanout` leaves the parent `pending` and nothing updates it as the
    children finish — so a parent reporting its own row would say `pending`
    over a finished run forever.
    """
    for job_id in ("job_one", "job_two", "job_three"):
        _finish(harness, job_id, "succeeded")
    stored = store.get(harness.conn, "job_parent")  # type: ignore[arg-type]

    assert stored is not None
    assert stored["status"] == "pending"  # the stale second source of truth
    assert harness.get("/jobs/job_parent")["status"] == "succeeded"


def test_a_leaf_answers_for_itself_with_no_progress(harness: Harness) -> None:
    # inventing `0 of 0` would put a progress bar on every single-stage job
    _finish(harness, "job_alone", "succeeded")

    answer = harness.get("/jobs/job_alone")

    assert answer["status"] == "succeeded"
    assert "progress" not in answer


def test_the_children_are_listed(harness: Harness) -> None:
    _finish(harness, "job_two", "failed")

    children = harness.client.get(
        "/jobs/job_parent/children", headers=harness.headers
    ).json()

    # created_at is identical for a fan-out's leaves, so the tiebreak is id
    assert [child["id"] for child in children] == [
        "job_one",
        "job_three",
        "job_two",
    ]
    assert [child["status"] for child in children] == [
        "pending",
        "pending",
        "failed",
    ]


def test_children_of_an_unknown_job_is_a_404(harness: Harness) -> None:
    response = harness.client.get(
        "/jobs/job_nope/children", headers=harness.headers
    )

    assert response.status_code == 404


def test_the_cli_shows_the_derived_status_and_progress(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from hrono import cli

    _finish(harness, "job_one", "succeeded")

    class Wired:
        def get(self, path: str, **_: object) -> object:
            return harness.get(path)

    monkeypatch.setattr("hrono.jobs.commands.from_profile", lambda: Wired())
    result = CliRunner().invoke(cli.app, ["jobs", "get", "job_parent"])

    assert result.exit_code == 0
    assert "partial" in result.output
    assert "1 of 3 stages done" in result.output


def test_the_cli_says_nothing_about_progress_for_a_leaf(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    from typer.testing import CliRunner

    from hrono import cli

    _finish(harness, "job_alone", "succeeded")

    class Wired:
        def get(self, path: str, **_: object) -> object:
            return harness.get(path)

    monkeypatch.setattr("hrono.jobs.commands.from_profile", lambda: Wired())
    result = CliRunner().invoke(cli.app, ["jobs", "get", "job_alone"])

    assert result.exit_code == 0
    assert "progress" not in result.output
