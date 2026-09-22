"""#138: the one operator verb, and the surface defects that shipped with it."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.jobs import store as jobs_store
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


def test_sync_enqueues_the_chain_and_returns_a_job(harness: Harness) -> None:
    # THE operator verb: one call brings an existing tree up to date.
    response = harness.client.post(
        "/trees/default/sync", headers=harness.auth("writer")
    )

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    with harness.client.app.state.db.connect() as conn:  # type: ignore[attr-defined]
        row = jobs_store.get(conn, job_id)
    assert row["op"] == "sync-tree"
    assert row["tree"] == "default"


def test_sync_needs_the_writer_role(harness: Harness) -> None:
    response = harness.client.post(
        "/trees/default/sync", headers=harness.auth("reader")
    )

    assert response.status_code == 403


def test_sync_and_maintain_stay_separate(harness: Harness) -> None:
    # a cold build and an update have very different costs; conflating them is
    # how a user pays for a rebuild by accident.
    synced = harness.client.post(
        "/trees/default/sync", headers=harness.auth("writer")
    ).json()["job_id"]
    built = harness.client.post(
        "/trees/default/maintain", headers=harness.auth("writer")
    ).json()["job_id"]

    with harness.client.app.state.db.connect() as conn:  # type: ignore[attr-defined]
        ops = {jobs_store.get(conn, job)["op"] for job in (synced, built)}
    assert ops == {"sync-tree", "maintain"}


def _prompt(name: str) -> dict[str, object]:
    return {"name": name, "role": "brief", "template": "X {content}"}


def test_put_creates_when_absent(harness: Harness) -> None:
    # "config is data you PUT" — it used to 404 unless the name already
    # existed, so writing config meant knowing whether it was there first.
    response = harness.client.put(
        "/prompts/fresh",
        json=_prompt("fresh"),
        headers=harness.auth("admin"),
    )

    assert response.status_code == 200
    assert (
        harness.client.get(
            "/prompts/fresh", headers=harness.auth("reader")
        ).status_code
        == 200
    )


def test_put_replaces_when_present_and_is_idempotent(
    harness: Harness,
) -> None:
    body = _prompt("twice")
    first = harness.client.put(
        "/prompts/twice", json=body, headers=harness.auth("admin")
    )
    body["template"] = "Y {content}"
    second = harness.client.put(
        "/prompts/twice", json=body, headers=harness.auth("admin")
    )

    assert (first.status_code, second.status_code) == (200, 200)
    stored = harness.client.get(
        "/prompts/twice", headers=harness.auth("reader")
    ).json()
    assert stored["template"] == "Y {content}"
    assert (
        len(
            [
                row
                for row in harness.client.get(
                    "/prompts", headers=harness.auth("reader")
                ).json()
                if row["name"] == "twice"
            ]
        )
        == 1
    )  # created once, not twice


def test_post_still_refuses_to_overwrite(harness: Harness) -> None:
    # POST keeps its create-only meaning for a caller that wants to be told.
    harness.client.post(
        "/prompts", json=_prompt("once"), headers=harness.auth("admin")
    )
    again = harness.client.post(
        "/prompts", json=_prompt("once"), headers=harness.auth("admin")
    )

    assert again.status_code == 409


def test_a_bad_query_parameter_uses_the_app_envelope(
    harness: Harness,
) -> None:
    # body validation already returned {"error": {...}}; a bad query parameter
    # escaped as FastAPI's raw {"detail": [...]}, so a client had to parse two
    # shapes depending on which half of the request was wrong.
    response = harness.client.get(
        "/trees/default/export?levels=abc", headers=harness.auth("reader")
    )

    assert response.status_code == 422
    body = response.json()
    assert "detail" not in body
    assert body["error"]["code"] == "validation-error"
    assert body["error"]["details"]["errors"]
