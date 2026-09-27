"""#187 (T55, tables half): config on the page, with secrets masked.

The masking is asserted against a REAL encrypted token written through the real
registry path — a placeholder would prove the template and nothing about
whether a credential can reach a browser.
"""

from __future__ import annotations

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
from hrono.registry import store as registry_store
from hrono.registry.collections import COLLECTIONS
from hrono.registry.seeding import seed_defaults
from hrono.registry.write import MASK
from hrono.server.app import create_app

KEY = Fernet.generate_key()
# Deliberately not vendor-shaped. What this test needs is a REAL Fernet
# ciphertext in the row, not a realistic prefix, and a literal that looks like
# a credential trips secret scanners on every tool that reads this file.
CONNECTION_KEY = "a-provider-key-that-must-not-reach-a-browser"
TOKEN = "a-provider-token-that-must-not-reach-a-browser"


class Browser:
    def __init__(self, client: TestClient, tokens: dict, conn: object) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn

    def sign_in(self, role: str = "admin") -> None:
        self.client.post("/ui/login", data={"token": self.tokens[role]})

    def config(self) -> str:
        return self.client.get("/ui/config").text


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[Browser]:
    conn = open_database(tmp_path / "hrono.db")
    record = reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1] for role in ("reader", "admin")
    }
    cipher = Cipher.from_key(KEY, record.key_id)
    # the seeder `hrono serve` itself runs (#021), not a planted is_default row
    seed_defaults(conn, cipher, COLLECTIONS)
    secret = cipher.encrypt(TOKEN)
    registry_store.insert(
        conn,
        "sources",
        "gh",
        json.dumps(
            {
                "name": "gh",
                "type": "git",
                "url": "https://github.com/x/y.git",
                "auth": {"method": "token", "token": secret.ciphertext},
            }
        ),
        secret.key_id,
        "t",
    )
    conn_secret = cipher.encrypt(CONNECTION_KEY)
    registry_store.insert(
        conn,
        "connections",
        "claude",
        json.dumps(
            {
                "name": "claude",
                "type": "anthropic",
                "auth": {"method": "key", "key": conn_secret.ciphertext},
            }
        ),
        conn_secret.key_id,
        "t",
    )
    registry_store.insert(
        conn,
        "trees",
        "alpha",
        json.dumps({"name": "alpha", "sources": ["gh"]}),
        None,
        "t",
    )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Browser(client, tokens, conn)
    conn.close()


def test_every_collection_is_listed(browser: Browser) -> None:
    browser.sign_in()

    page = browser.config()

    for collection in ("sources", "connections", "models", "prompts", "trees"):
        assert f">{collection}</h2>" in page


def test_a_configured_item_is_shown(browser: Browser) -> None:
    browser.sign_in()

    page = browser.config()

    assert "gh" in page
    assert "https://github.com/x/y.git" in page
    assert "alpha" in page


def test_a_secret_is_masked_and_so_is_its_ciphertext(
    browser: Browser,
) -> None:
    """Neither the plaintext nor the STORED ciphertext reaches the page.

    The plaintext could not reach it anyway — the row holds ciphertext — so the
    assertion that carries the weight is the ciphertext one: `mask()` replaces
    the field, rather than the page merely happening not to decrypt it.
    """
    browser.sign_in()

    page = browser.config()

    stored = json.loads(
        registry_store.get(browser.conn, "sources", "gh")["config"]  # type: ignore[arg-type,index]
    )
    assert TOKEN not in page
    assert stored["auth"]["token"] not in page
    assert MASK in page


def test_a_seeded_default_is_marked(browser: Browser) -> None:
    # prompts are seeded (#021); saying which are defaults is how an operator
    # knows what they have actually changed
    browser.sign_in()

    page = browser.config()

    assert "(default)" in page


def test_each_collection_is_masked_by_its_own_declared_paths(
    browser: Browser,
) -> None:
    """A connection's key is at `auth.key`, a source's token at `auth.token`.

    Masking every row with ONE collection's descriptor would leave the page
    looking right for sources — the first collection — while leaking every
    other collection's credential.
    """
    browser.sign_in()

    page = browser.config()

    stored = json.loads(
        registry_store.get(browser.conn, "connections", "claude")["config"]  # type: ignore[arg-type,index]
    )
    assert CONNECTION_KEY not in page
    assert stored["auth"]["key"] not in page
    assert page.count(MASK) == 2  # the source's token and the connection's key


def test_an_empty_collection_says_so(browser: Browser) -> None:
    browser.sign_in()

    assert "no models configured." in browser.config()


def test_a_reader_can_see_config(browser: Browser) -> None:
    # nothing here writes, so nothing here needs a writer
    browser.sign_in("reader")

    assert browser.client.get("/ui/config").status_code == 200


def test_the_page_needs_a_login(browser: Browser) -> None:
    answer = browser.client.get("/ui/config", follow_redirects=False)

    assert answer.status_code == 303
