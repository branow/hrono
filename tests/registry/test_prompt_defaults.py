import json
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
from hrono.registry.collections.prompts import PROMPTS
from hrono.registry.seeding import seed_defaults
from hrono.registry.write import content_hash
from hrono.server.app import create_app

KEY = Fernet.generate_key()
ROLES = {"condense", "brief", "brief-upper", "judge"}


def _cipher() -> Cipher:
    return Cipher.from_key(KEY, 1)


def test_seed_creates_one_default_per_role(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    seed_defaults(conn, _cipher(), (PROMPTS,))
    names = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM registry WHERE collection = 'prompts'"
        )
    }
    assert names == ROLES
    conn.close()


def test_reseed_is_idempotent_and_never_overwrites(tmp_path: Path) -> None:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    seed_defaults(conn, _cipher(), (PROMPTS,))
    store.replace(
        conn,
        "prompts",
        "condense",
        json.dumps(
            {"name": "condense", "role": "condense", "template": "MINE"}
        ),
        None,
        "now",
        "h",
    )
    seed_defaults(conn, _cipher(), (PROMPTS,))
    count = conn.execute(
        "SELECT count(*) FROM registry WHERE collection = 'prompts'"
    ).fetchone()[0]
    assert count == 4
    kept = store.get(conn, "prompts", "condense")
    assert json.loads(kept["config"])["template"] == "MINE"
    conn.close()


class Harness:
    def __init__(self, client: TestClient, conn: object, token: str) -> None:
        self.client = client
        self.conn = conn
        self.headers = {"Authorization": f"Bearer {token}"}


@pytest.fixture
def harness(tmp_path: Path) -> Iterator[Harness]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "writer", "writer")[1]
    seed_defaults(conn, _cipher(), (PROMPTS,))
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Harness(client, conn, token)
    conn.close()


def default_template(name: str) -> str:
    return next(
        str(d["template"]) for d in PROMPTS.defaults if d["name"] == name
    )


def test_delete_of_a_default_resets_it(harness: Harness) -> None:
    removed = harness.client.delete(
        "/prompts/condense", headers=harness.headers
    )
    assert removed.status_code == 200
    assert removed.json() == {"reset": "condense"}
    fetched = harness.client.get("/prompts/condense", headers=harness.headers)
    assert fetched.status_code == 200
    assert fetched.json()["template"] == default_template("condense")


def test_delete_of_a_user_prompt_removes_it(harness: Harness) -> None:
    harness.client.post(
        "/prompts",
        json={
            "name": "mine",
            "role": "judge",
            "template": "T {source} {summary}",
        },
        headers=harness.headers,
    )
    assert (
        harness.client.delete(
            "/prompts/mine", headers=harness.headers
        ).status_code
        == 200
    )
    assert (
        harness.client.get("/prompts/mine", headers=harness.headers).status_code
        == 404
    )


def test_override_then_delete_restores_the_default(harness: Harness) -> None:
    harness.client.put(
        "/prompts/brief",
        json={
            "name": "brief",
            "role": "brief",
            "template": "OVERRIDE {content}",
        },
        headers=harness.headers,
    )
    assert (
        harness.client.get("/prompts/brief", headers=harness.headers).json()[
            "template"
        ]
        == "OVERRIDE {content}"
    )
    harness.client.delete("/prompts/brief", headers=harness.headers)
    restored = harness.client.get(
        "/prompts/brief", headers=harness.headers
    ).json()["template"]
    assert restored == default_template("brief")
    assert "{content}" in restored  # the restored default is a valid template


def test_template_hash_updates_on_write(harness: Harness) -> None:
    harness.client.post(
        "/prompts",
        json={
            "name": "h",
            "role": "judge",
            "template": "one {source} {summary}",
        },
        headers=harness.headers,
    )
    first = harness.conn.execute(
        "SELECT content_hash FROM registry WHERE name = 'h'"
    ).fetchone()["content_hash"]
    harness.client.put(
        "/prompts/h",
        json={
            "name": "h",
            "role": "judge",
            "template": "two {source} {summary}",
        },
        headers=harness.headers,
    )
    second = harness.conn.execute(
        "SELECT content_hash FROM registry WHERE name = 'h'"
    ).fetchone()["content_hash"]
    assert first and second and first != second


def _shipped_upper() -> str:
    return next(d for d in PROMPTS.defaults if d["name"] == "brief-upper")[
        "template"
    ]


def _hold_upper(conn, template: str, *, hash_of_old: bool) -> None:
    payload = json.dumps(
        {"name": "brief-upper", "role": "brief-upper", "template": template}
    )
    digest = (
        PROMPTS.superseded["brief-upper"][0]
        if hash_of_old
        else content_hash(payload)
    )
    store.replace(conn, "prompts", "brief-upper", payload, None, "t", digest)


def test_upgrade_replaces_an_untouched_old_upper_default(
    tmp_path: Path,
) -> None:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    seed_defaults(conn, _cipher(), (PROMPTS,))
    _hold_upper(conn, "OLD {content}", hash_of_old=True)
    seed_defaults(conn, _cipher(), (PROMPTS,))
    row = store.get(conn, "prompts", "brief-upper")
    assert json.loads(row["config"])["template"] == _shipped_upper()
    assert row["is_default"] == 1
    conn.close()


def test_upgrade_leaves_an_edited_upper_prompt_as_written(
    tmp_path: Path,
) -> None:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    seed_defaults(conn, _cipher(), (PROMPTS,))
    _hold_upper(conn, "MINE {content}", hash_of_old=False)
    seed_defaults(conn, _cipher(), (PROMPTS,))
    row = store.get(conn, "prompts", "brief-upper")
    assert json.loads(row["config"])["template"] == "MINE {content}"
    conn.close()


# The brief-upper default hrono first shipped (2026-10-09); the flask bench
# registry still holds it, untouched.
FIRST_UPPER = (
    "Summarize the child briefs below into one higher-level brief for a "
    "parent node. Keep concrete names and routing signal; drop detail that "
    "only matters within a single child.\n\n{content}"
)


def test_upgrade_replaces_every_earlier_shipped_upper_default(
    tmp_path: Path,
) -> None:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    seed_defaults(conn, _cipher(), (PROMPTS,))
    _hold_upper(conn, FIRST_UPPER, hash_of_old=False)
    seed_defaults(conn, _cipher(), (PROMPTS,))
    row = store.get(conn, "prompts", "brief-upper")
    assert json.loads(row["config"])["template"] == _shipped_upper()
    conn.close()
