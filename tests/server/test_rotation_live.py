"""E021: a rotation moves the RUNNING server onto the new key.

Every test saves a secret through the endpoint AFTER rotating and then reopens
the database on the new key, the way a restart does: a secret left on the old
key is a `KeyMismatch` there, which is the half-rotated state.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database, open_database
from hrono.registry import store
from hrono.registry.collections import CONNECTIONS
from hrono.registry.engine import create_item, delete_item, replace_item
from hrono.registry.validation import connection_validation
from hrono.registry.write import decrypt, encrypt
from hrono.server.app import create_app
from hrono.server.rotation import rotate_running

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
    assert server.rotate().status_code == 200
    assert server.save().status_code == 201
    assert restarted_on_new_key(server.db) == "sk-saved-after-rotation"


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
    cipher = server.client.app.state.cipher  # type: ignore[attr-defined]
    before = cipher.encrypt("x").key_id
    assert server.rotate(old=Fernet.generate_key()).status_code == 403
    assert server.rotate(new=b"not-a-key").status_code == 400
    assert cipher.encrypt("x").key_id == before
    assert server.save().status_code == 201
    conn = open_database(server.db)
    try:
        assert reconcile(conn, KEY).key_id == before
        assert store.get(conn, "connections", "late")["key_id"] == before  # type: ignore[index]
    finally:
        conn.close()


class SeamDb:
    """The injected database: a hook before each write and a probe at its end.

    `before` runs as a writer asks for the lock; `at_exit` runs inside the
    lock, as the block ends and just before it commits.
    """

    def __init__(self, real: Database) -> None:
        self.real = real
        self.before = lambda: None
        self.at_exit = lambda: None

    @contextmanager
    def write(self) -> Iterator[sqlite3.Connection]:
        self.before()
        with self.real.write() as conn:
            yield conn
            self.at_exit()

    def connect(self):  # type: ignore[no-untyped-def]
        return self.real.connect()

    def close(self) -> None:
        self.real.close()


def _seam(tmp_path: Path) -> tuple[Path, SeamDb, Cipher]:
    path = tmp_path / "hrono.db"
    with open_database(path) as setup:
        record = reconcile(setup, KEY)
    return (
        path,
        SeamDb(Database.at(path)),
        Cipher.from_key(KEY, record.key_id),
    )


def test_the_swap_is_made_before_the_rotation_commits(tmp_path: Path) -> None:
    """A writer queued on the lock gets it the instant the rotation commits.

    So the cipher must already be on the new key when the block ends: a rekey
    placed after it leaves a window where that writer seals on the old key.
    """
    _path, seam, cipher = _seam(tmp_path)
    app = SimpleNamespace(state=SimpleNamespace(db=seam, cipher=cipher))
    seen: list[int] = []
    seam.at_exit = lambda: seen.append(cipher.encrypt("x").key_id)
    result = rotate_running(app, KEY, FRESH)  # type: ignore[arg-type]
    seam.close()
    assert seen == [result.key_id]


@pytest.mark.parametrize("writer", ["create", "replace", "delete"])
def test_a_write_in_flight_across_a_rotation_lands_on_the_new_key(
    tmp_path: Path, writer: str
) -> None:
    """The rotation commits after the write is prepared, before it writes.

    One case per engine writer, through the real engine, descriptor and
    rotation. The rotation fires as the writer asks for the write lock (the
    database's `write` is the seam), so a writer that sealed its secret
    before asking lands on the old key: a KeyMismatch after the restart.
    """
    path, seam, cipher = _seam(tmp_path)
    db = seam.real
    app = SimpleNamespace(
        state=SimpleNamespace(db=seam, cipher=cipher, cache_root=None)
    )
    request = SimpleNamespace(app=app)
    fired: list[bool] = []

    def rotate_once() -> None:
        if not fired:
            fired.append(True)
            rotate_running(app, KEY, FRESH)  # type: ignore[arg-type]

    default = {
        "name": "late",
        "provider": "anthropic",
        "auth": {"method": "api-key", "key": "sk-saved-after-rotation"},
    }
    descriptor = replace(CONNECTIONS, validate=None, defaults=(default,))
    if writer != "create":
        stored, key_id = encrypt(default, descriptor, cipher)
        with db.write() as conn:
            store.insert(
                conn,
                "connections",
                "late",
                json.dumps(stored),
                key_id,
                "2026-01-01",
                is_default=1,
            )
    seam.before = rotate_once
    body = default
    {
        "create": lambda: create_item(descriptor, body, request),  # type: ignore[arg-type]
        "replace": lambda: replace_item(descriptor, "late", body, request),  # type: ignore[arg-type]
        "delete": lambda: delete_item(descriptor, "late", request),  # type: ignore[arg-type]
    }[writer]()
    db.close()
    assert fired
    assert restarted_on_new_key(path) == "sk-saved-after-rotation"
