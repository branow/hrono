"""#197: the vocabulary had nowhere to live.

Every other page runs to a tight prose budget — a hint beside the thing, never
a paragraph above it. That rule only works if the explanation has somewhere to
BE, and it had nowhere: the words were defined in a spec outside the repository
and in a gitignored working file, so a person looking at the map could not find
out what a topic was without asking someone.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.server.app import create_app

KEY = Fernet.generate_key()
TREE = "default"


class Browser:
    def __init__(self, client: TestClient, tokens: dict, conn: object) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn

    def sign_in(self, role: str = "admin") -> None:
        self.client.post("/ui/login", data={"token": self.tokens[role]})

    def guide(self) -> str:
        return self.client.get("/ui/guide").text


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[Browser]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1] for role in ("reader", "admin")
    }
    with conn:
        # THREE sections in ONE topic, deliberately: with one of each, a count
        # that read the wrong table would give the right answer anyway
        sections = []
        for name in ("a.md", "b.md", "c.md"):
            body = f"a section of the corpus: {name}\n".encode()
            digest = content_hash(body)
            istore.upsert_content(conn, digest, body)
            sections.append(
                istore.insert_section(
                    conn,
                    source="docs",
                    address=Address("git", "ex/docs", name, "v1"),
                    start=0,
                    end=len(body),
                    content_hash=digest,
                    ordinal=0,
                )
            )
        cluster_store.add_leaf_node(
            conn, TREE, [(s, False, None) for s in sections]
        )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        yield Browser(client, tokens, conn)
    conn.close()


def test_the_guide_defines_every_word_the_ui_uses(browser: Browser) -> None:
    """A word on the screen that is nowhere explained is the complaint."""
    browser.sign_in()

    page = browser.guide()

    for word in (
        "topic",
        "section",
        "condensation",
        "brief",
        "passage",
        "tree",
        "stale",
        "pin",
        "parked",
        "misfit",
    ):
        assert f"<dt>{word}</dt>" in page, word


def test_it_says_which_words_are_NOT_used(browser: Browser) -> None:
    """The reason this page exists: the owner could not remember whether the
    word was chunk or section, and nothing told him."""
    browser.sign_in()

    page = browser.guide()

    assert "cluster" in page
    assert "Chunk" in page and "earlier name" in page


def test_the_counts_are_this_install_not_a_description(
    browser: Browser,
) -> None:
    """A pipeline explained in the abstract is a diagram; explained in the
    numbers it actually produced, it is a status."""
    browser.sign_in()

    page = browser.guide()
    steps = re.findall(
        r'class="step-mark">([a-z]+)</span>.*?class="step-count">(\d+)<',
        page,
        re.S,
    )

    assert dict(steps)["section"] == "3"
    assert dict(steps)["topic"] == "1"  # three sections, one topic
    assert dict(steps)["condensation"] == "0"  # nothing has condensed yet


def test_a_reader_can_read_it(browser: Browser) -> None:
    # it explains, it does not change anything
    browser.sign_in("reader")

    assert browser.client.get("/ui/guide").status_code == 200


def test_it_is_reachable_from_every_page(browser: Browser) -> None:
    """A page nothing links to is a page nobody finds."""
    browser.sign_in()

    for path in ("/ui", "/ui/jobs", "/ui/config"):
        assert "/ui/guide?tree=" in browser.client.get(path).text, path


def test_signing_out_is_still_required(browser: Browser) -> None:
    answer = browser.client.get("/ui/guide", follow_redirects=False)

    assert answer.status_code == 303


def test_the_repository_ships_the_same_vocabulary(browser: Browser) -> None:
    """The page is for a person using it; GLOSSARY.md is for a person who has
    cloned it. They must not drift, so the words are checked against both."""
    glossary = Path(__file__).resolve().parents[2] / "GLOSSARY.md"

    text = glossary.read_text()

    for word in ("section", "condensation", "topic", "brief", "passage"):
        assert f"**{word}**" in text, word
    assert "Superseded name: **chunk**" in text
