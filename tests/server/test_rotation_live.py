"""E021: a rotation moves the RUNNING server onto the new key.

Every test saves a secret through the endpoint AFTER rotating and then reopens
the database on the new key, the way a restart does: a secret left on the old
key is a `KeyMismatch` there, which is the half-rotated state.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.registry import store
from hrono.registry.collections import CONNECTIONS
from hrono.registry.validation import connection_validation
from hrono.registry.write import decrypt
from hrono.server.app import create_app

KEY = Fernet.generate_key()
FRESH = Fernet.generate_key()
CONNECTION = {
    "name": "late",
    "provider": "anthropic",
    "auth": {"method": "api-key", "key": "sk-saved-after-rotation"},
}


@pytest.fixture(autouse=True)
def _valid_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("_get", "_bearer_get"):
        monkeypatch.setattr(
            connection_validation, name, lambda url, key, timeout: 200
        )


class Server:
    def __init__(self, client: TestClient, db: Path, admin: str) -> None:
        self.client = client
        self.db = db
        self.headers = {"Authorization": f"Bearer {admin}"}

    def rotate(self, old: bytes = KEY, new: bytes = FRESH):  # type: ignore[no-untyped-def]
        return self.client.post(
            "/admin/rotate-key",
            json={"old_key": old.decode(), "new_key": new.decode()},
            headers=self.headers,
        )

    def save(self):  # type: ignore[no-untyped-def]
        return self.client.post(
            "/connections", json=CONNECTION, headers=self.headers
        )


@pytest.fixture
def server(tmp_path: Path) -> Iterator[Server]:
    path = tmp_path / "hrono.db"
    with open_database(path) as setup:
        reconcile(setup, KEY)
        admin = create_user(setup, "admin", "admin")[1]
    with TestClient(create_app(db_path=path, master_key=KEY)) as client:
        yield Server(client, path, admin)


def restarted_on_new_key(db: Path) -> str:
    conn = open_database(db)
    try:
        record = reconcile(conn, FRESH)
        row = store.get(conn, "connections", "late")
        assert row is not None
        assert row["key_id"] == record.key_id
        return decrypt(
            json.loads(row["config"]),
            CONNECTIONS,
            Cipher.from_key(FRESH, record.key_id),
            int(row["key_id"]),
        )["auth"]["key"]  # type: ignore[index,return-value]
    finally:
        conn.close()


def test_a_secret_saved_after_rotation_survives_a_restart_on_the_new_key(
    server: Server,
) -> None:
    rotated = server.rotate()
    assert rotated.status_code == 200
    assert server.save().status_code == 201
    assert restarted_on_new_key(server.db) == "sk-saved-after-rotation"
    assert server.client.app.state.key_id == rotated.json()["key_id"]  # type: ignore[attr-defined]


def test_the_panel_rotation_switches_the_running_key_too(
    server: Server,
) -> None:
    server.client.post(
        "/ui/login", data={"token": server.headers["Authorization"][7:]}
    )
    done = server.client.post(
        "/ui/access/rotate-key",
        data={
            "old_key": KEY.decode(),
            "new_key": FRESH.decode(),
            "confirm": "1",
        },
    )
    assert done.status_code == 200
    assert "restart" in done.text
    assert server.save().status_code == 201
    assert restarted_on_new_key(server.db) == "sk-saved-after-rotation"


def test_a_refused_rotation_leaves_the_running_key_unchanged(
    server: Server,
) -> None:
    state = server.client.app.state  # type: ignore[attr-defined]
    before = state.key_id
    assert server.rotate(old=Fernet.generate_key()).status_code == 403
    assert server.rotate(new=b"not-a-key").status_code == 400
    assert state.key_id == before
    assert server.save().status_code == 201
    conn = open_database(server.db)
    try:
        assert reconcile(conn, KEY).key_id == before
        assert store.get(conn, "connections", "late")["key_id"] == before  # type: ignore[index]
    finally:
        conn.close()


def test_a_save_in_flight_across_a_rotation_lands_on_the_new_key(
    server: Server, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rotation commits after the save is prepared, before it writes."""
    from hrono.server.rotation import rotate_running

    app = server.client.app
    db = app.state.db  # type: ignore[attr-defined]
    real = db.write
    fired = []

    def rotate_then_write():  # type: ignore[no-untyped-def]
        # the auth layer writes too; only the registry's own write counts
        if not fired and sys._getframe(1).f_code.co_name == "create_item":
            fired.append(True)
            rotate_running(app, KEY, FRESH)  # type: ignore[arg-type]
        return real()

    monkeypatch.setattr(db, "write", rotate_then_write)
    assert server.save().status_code == 201
    assert fired
    assert restarted_on_new_key(server.db) == "sk-saved-after-rotation"
