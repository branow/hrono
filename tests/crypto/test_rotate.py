"""#177 (T59): rotating the master key.

Every test drives the rotation through the ENDPOINT and then reads the secret
back through the registry's own decrypt path (#176) — a rotation that leaves
rows nothing can read is the failure mode, so reading them back is the test.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.cipher import Cipher, KeyMismatch
from hrono.crypto.masterkey import reconcile
from hrono.crypto.rotate import rotate
from hrono.db.database import open_database
from hrono.registry import store
from hrono.registry.sources import SOURCES
from hrono.registry.write import decrypt
from hrono.server.app import create_app

OLD = Fernet.generate_key()
NEW = Fernet.generate_key()
TOKEN = "ghp_a_provider_token_that_must_survive"


class Harness:
    def __init__(self, client: TestClient, tokens: dict, conn: object) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn

    def auth(self, role: str) -> dict:
        return {"Authorization": f"Bearer {self.tokens[role]}"}

    def rotate(
        self, old: bytes = OLD, new: bytes = NEW, role: str = "admin"
    ) -> object:
        return self.client.post(
            "/admin/rotate-key",
            json={"old_key": old.decode(), "new_key": new.decode()},
            headers=self.auth(role),
        )

    def row(self, name: str = "gh") -> object:
        return store.get(self.conn, "sources", name)  # type: ignore[arg-type]

    def secret_under(self, key: bytes, name: str = "gh") -> str:
        row = self.row(name)
        plain = decrypt(
            json.loads(row["config"]),  # type: ignore[index]
            SOURCES,
            Cipher.from_key(key, int(row["key_id"])),  # type: ignore[index]
            int(row["key_id"]),  # type: ignore[index]
        )
        return str(plain["auth"]["token"])  # type: ignore[index,call-overload]


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    conn = open_database(tmp_path / "hrono.db")
    record = reconcile(conn, OLD)
    tokens = {
        role: create_user(conn, role, role)[1] for role in ("writer", "admin")
    }
    cipher = Cipher.from_key(OLD, record.key_id)
    secret = cipher.encrypt(TOKEN)
    store.insert(
        conn,
        "sources",
        "gh",
        json.dumps(
            {
                "name": "gh",
                "type": "github-repo",
                "url": "https://github.com/x/y.git",
                "auth": {"token": secret.ciphertext},
            }
        ),
        secret.key_id,
        "t",
    )
    store.insert(
        conn,
        "prompts",
        "brief",
        json.dumps({"name": "brief", "role": "brief", "template": "{content}"}),
        None,
        "t",
    )
    app = create_app(connection=conn, master_key=OLD, key_id=record.key_id)
    with TestClient(app) as client:
        yield Harness(client, tokens, conn)
    conn.close()


def test_every_secret_moves_to_the_new_key_unchanged(
    harness: Harness,
) -> None:
    before = harness.row()["key_id"]  # type: ignore[index]

    response = harness.rotate()

    assert response.status_code == 200  # type: ignore[attr-defined]
    body = response.json()  # type: ignore[attr-defined]
    assert body["rotated"] == 1
    assert body["key_id"] != before
    assert harness.row()["key_id"] == body["key_id"]  # type: ignore[index]
    # the whole point: the plaintext survives the journey
    assert harness.secret_under(NEW) == TOKEN


def test_the_old_key_can_no_longer_read_it(harness: Harness) -> None:
    harness.rotate()

    with pytest.raises(Exception):  # noqa: B017 - KeyMismatch or InvalidToken
        harness.secret_under(OLD)


def test_a_wrong_old_key_changes_nothing(harness: Harness) -> None:
    # proof of possession: without it, anyone reaching this endpoint can
    # re-encrypt the corpus under a key they chose and lock the owner out.
    before = json.loads(harness.row()["config"])  # type: ignore[index]

    response = harness.rotate(old=Fernet.generate_key())

    assert response.status_code == 403  # type: ignore[attr-defined]
    assert json.loads(harness.row()["config"]) == before  # type: ignore[index]
    assert harness.secret_under(OLD) == TOKEN


def test_an_unusable_new_key_is_refused_before_anything_is_written(
    harness: Harness,
) -> None:
    before = harness.row()["key_id"]  # type: ignore[index]

    response = harness.client.post(
        "/admin/rotate-key",
        json={"old_key": OLD.decode(), "new_key": "not-a-key"},
        headers=harness.auth("admin"),
    )

    assert response.status_code == 400
    assert harness.row()["key_id"] == before  # type: ignore[index]
    assert _key_count(harness) == 1  # no orphan key row either


def test_a_secretless_row_is_left_alone(harness: Harness) -> None:
    # prompts carry no secret and no key_id; rotating must not invent one.
    harness.rotate()

    prompt = store.get(harness.conn, "prompts", "brief")  # type: ignore[arg-type]

    assert prompt is not None
    assert prompt["key_id"] is None


def test_rotation_is_admin_only(harness: Harness) -> None:
    response = harness.rotate(role="writer")

    assert response.status_code == 403  # type: ignore[attr-defined]
    assert harness.secret_under(OLD) == TOKEN


def test_no_key_reaches_the_response_or_the_row(harness: Harness) -> None:
    response = harness.rotate()

    body = response.text  # type: ignore[attr-defined]
    assert OLD.decode() not in body
    assert NEW.decode() not in body
    stored = json.dumps(
        [dict(row) for row in store.list_all(harness.conn, "sources")]  # type: ignore[arg-type]
    )
    assert OLD.decode() not in stored
    assert NEW.decode() not in stored


def test_the_response_says_the_running_server_is_now_blind(
    harness: Harness,
) -> None:
    """Not just "update the key file" — say what is broken until they do.

    Every secret is on the new key and this process holds the old one, so it
    can decrypt NOTHING (`KeyMismatch`). Masked reads still answer 200, which
    is exactly what makes that easy to miss.
    """
    body = harness.rotate().json()  # type: ignore[attr-defined]

    assert "key file" in body["next"]
    assert "RESTART" in body["next"]
    assert "credential" in body["next"]


def test_the_running_server_really_is_blind_until_it_restarts(
    harness: Harness,
) -> None:
    harness.rotate()
    row = harness.row()

    with pytest.raises(KeyMismatch):
        decrypt(
            json.loads(row["config"]),  # type: ignore[index]
            SOURCES,
            Cipher.from_key(OLD, 1),  # what this process still holds
            int(row["key_id"]),  # type: ignore[index]
        )

    # and a masked read still answers, which is the trap
    assert (
        harness.client.get(
            "/sources/gh", headers=harness.auth("admin")
        ).status_code
        == 200
    )


def _key_count(harness: Harness) -> int:
    return int(
        harness.conn.execute(  # type: ignore[attr-defined]
            "SELECT COUNT(*) FROM keys"
        ).fetchone()[0]
    )


def test_a_failure_part_way_leaves_every_row_on_the_old_key(
    harness: Harness,
) -> None:
    """All or nothing, driven rather than argued.

    The server holds ONE cipher, so a row left on the other key raises
    `KeyMismatch` and is readable by neither side. A half-rotated database is
    worse than an unrotated one, and the only thing standing between them is
    that the whole walk is inside one transaction.
    """
    # a second source whose ciphertext is corrupt: it decrypts under no key
    store.insert(
        harness.conn,  # type: ignore[arg-type]
        "sources",
        "broken",
        json.dumps(
            {
                "name": "broken",
                "type": "github-repo",
                "url": "https://github.com/x/z.git",
                "auth": {"token": "not-a-fernet-token"},
            }
        ),
        int(harness.row()["key_id"]),  # type: ignore[index]
        "t",
    )
    before = int(harness.row()["key_id"])  # type: ignore[index]

    response = harness.rotate()

    assert response.status_code >= 400  # type: ignore[attr-defined]
    # the GOOD row is untouched, and still readable with the key the operator
    # still has in their key file
    assert int(harness.row()["key_id"]) == before  # type: ignore[index]
    assert harness.secret_under(OLD) == TOKEN
    assert _key_count(harness) == 1  # and no new key row was left behind


def test_a_source_with_no_secret_at_all_is_left_alone(
    harness: Harness,
) -> None:
    # a PUBLIC repo has `auth: null`, so its row carries no key_id. Rotating it
    # would decrypt under `int(None)`; the skip is not hypothetical.
    store.insert(
        harness.conn,  # type: ignore[arg-type]
        "sources",
        "public",
        json.dumps(
            {
                "name": "public",
                "type": "github-repo",
                "url": "https://github.com/x/public.git",
                "auth": None,
            }
        ),
        None,
        "t",
    )

    body = harness.rotate().json()  # type: ignore[attr-defined]

    assert body["rotated"] == 1  # the secret-bearing one, not this
    public = store.get(harness.conn, "sources", "public")  # type: ignore[arg-type]
    assert public is not None
    assert public["key_id"] is None


def test_rotate_is_atomic_for_a_caller_with_no_outer_transaction(
    tmp_path: Path,
) -> None:
    """The inner transaction, proved on its own.

    Through the endpoint, the route's `database.write()` already rolls a
    failure back — so the route's transaction, not this function's, is what a
    test through the API measures. `rotate` is also callable directly, and this
    is the caller its own `with conn` protects.
    """
    conn = open_database(tmp_path / "hrono.db")
    record = reconcile(conn, OLD)
    cipher = Cipher.from_key(OLD, record.key_id)
    good = cipher.encrypt(TOKEN)
    for name, token in (("good", good.ciphertext), ("bad", "not-a-token")):
        store.insert(
            conn,
            "sources",
            name,
            json.dumps(
                {
                    "name": name,
                    "type": "github-repo",
                    "url": f"https://github.com/x/{name}.git",
                    "auth": {"token": token},
                }
            ),
            record.key_id,
            "t",
        )

    with pytest.raises(Exception):  # noqa: B017 - whatever the bad row raises
        rotate(conn, OLD, NEW)

    row = store.get(conn, "sources", "good")
    assert row is not None
    assert int(row["key_id"]) == record.key_id
    assert int(conn.execute("SELECT COUNT(*) FROM keys").fetchone()[0]) == 1
    conn.close()
