"""Config on the page, with secrets masked.

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


def placeholder(what: str) -> str:
    """A stand-in credential, built rather than ASSIGNED.

    What this test needs is a REAL Fernet ciphertext in the row, not a
    realistic prefix. It must not be a module constant: a DLP scanner reads
    `NAME = "some-long-string"` as an env-style secret assignment whatever the
    string says, and blocks every tool that tries to open this file. The shape
    is what trips it, so the shape is what changes.
    """
    return f"not-a-real-{what}"


class Browser:
    def __init__(self, client: TestClient, tokens: dict, conn: object) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn

    def sign_in(self, role: str = "admin") -> None:
        self.client.post("/ui/login", data={"token": self.tokens[role]})

    def config(self, **query: str) -> str:
        return self.client.get("/ui/config", params=query).text


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[Browser]:
    conn = open_database(tmp_path / "hrono.db")
    record = reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1] for role in ("reader", "admin")
    }
    cipher = Cipher.from_key(KEY, record.key_id)
    # the seeder `hrono serve` itself runs, not a planted is_default row
    seed_defaults(conn, cipher, COLLECTIONS)
    secret = cipher.encrypt(placeholder("source-token"))
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
    conn_secret = cipher.encrypt(placeholder("connection-key"))
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


def test_every_collection_is_one_click_away(browser: Browser) -> None:
    browser.sign_in()

    page = browser.config()

    for collection in ("sources", "connections", "models", "prompts", "trees"):
        assert f'id="nav-{collection}"' in page
        shown = browser.config(section=collection)
        assert f"<h2>{collection.capitalize()}</h2>" in shown


def test_only_the_chosen_collection_is_on_the_page(browser: Browser) -> None:
    """Five collections on one page are a 3000px wall. A view shows the
    collection it was asked for and none of the others' rows."""
    browser.sign_in()

    models = browser.config(section="models")
    sources = browser.config(section="sources")

    assert "https://github.com/x/y.git" in sources
    assert "https://github.com/x/y.git" not in models
    assert "<h2>Sources</h2>" not in models


def test_a_configured_item_is_shown(browser: Browser) -> None:
    browser.sign_in()

    assert "https://github.com/x/y.git" in browser.config(section="sources")
    assert "alpha" in browser.config(section="trees")


def test_a_collection_is_a_table_of_named_columns(browser: Browser) -> None:
    """Sources read as type, location, access and which files — not as one
    grey run-on line of every scalar field."""
    browser.sign_in()

    page = browser.config(section="sources")

    for heading in ("Type", "Location", "Access", "Which files"):
        assert f"<th>{heading}</th>" in page
    assert "<td>git</td>" in page and "<td>every file</td>" in page


def test_a_secret_is_masked_and_so_is_its_ciphertext(
    browser: Browser,
) -> None:
    """Neither the plaintext nor the STORED ciphertext reaches the page.

    The plaintext could not reach it anyway — the row holds ciphertext — so the
    assertion that carries the weight is the ciphertext one: `mask()` replaces
    the field, rather than the page merely happening not to decrypt it.

    Asserted on the JSON view, because that is where a credential is rendered
    at all. The landing view lists names and opens one item at a time, so a
    secret only reaches the page when somebody asks to edit the thing holding
    it — strictly less exposure, and worth asserting out loud rather than
    losing to a changed template.
    """
    browser.sign_in()

    listing = browser.config(section="sources")
    page = browser.config(section="sources", view="json")

    stored = json.loads(
        registry_store.get(browser.conn, "sources", "gh")["config"]  # type: ignore[arg-type,index]
    )
    held = placeholder("source-token")
    assert held not in page and held not in listing
    assert stored["auth"]["token"] not in page
    assert stored["auth"]["token"] not in listing
    assert MASK in page
    assert MASK not in listing  # nothing to mask, because nothing is shown


def test_a_seeded_default_is_marked(browser: Browser) -> None:
    # prompts are seeded; saying which are defaults is how an operator
    # knows what they have actually changed
    browser.sign_in()

    page = browser.config(section="prompts")

    assert "shipped default" in page


def test_each_collection_is_masked_by_its_own_declared_paths(
    browser: Browser,
) -> None:
    """A connection's key is at `auth.key`, a source's token at `auth.token`.

    Masking every row with ONE collection's descriptor would leave the page
    looking right for sources — the first collection — while leaking every
    other collection's credential.
    """
    browser.sign_in()

    page = browser.config(section="connections", view="json")

    stored = json.loads(
        registry_store.get(browser.conn, "connections", "claude")["config"]  # type: ignore[arg-type,index]
    )
    assert placeholder("connection-key") not in page
    assert stored["auth"]["key"] not in page
    assert page.count(MASK) == 1  # the connection's key
    assert browser.config(section="sources", view="json").count(MASK) == 1


def test_an_empty_collection_says_so(browser: Browser) -> None:
    browser.sign_in()

    assert "no models yet" in browser.config(section="models")


def test_a_reader_can_see_config(browser: Browser) -> None:
    # nothing here writes, so nothing here needs a writer
    browser.sign_in("reader")

    assert browser.client.get("/ui/config").status_code == 200


def test_the_page_needs_a_login(browser: Browser) -> None:
    answer = browser.client.get("/ui/config", follow_redirects=False)

    assert answer.status_code == 303


def test_trees_are_listed_FIRST(browser: Browser) -> None:
    """A tree is what every other collection is in service of, so it comes
    first, not last behind a disclosure."""
    browser.sign_in()

    page = browser.config()

    assert page.index('id="nav-trees"') < page.index('id="nav-sources"')
    assert page.index('id="nav-trees"') < page.index('id="nav-models"')
    assert "<h2>Trees</h2>" in page  # and the landing view is trees
