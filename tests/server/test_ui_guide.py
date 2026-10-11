"""The Guide page: the dashboard's vocabulary, in the dashboard.

Every other page runs to a tight prose budget — a hint beside the thing, never
a paragraph above it. That rule only works if the explanation has somewhere to
BE, inside the product, so a person looking at the map can find out what a
topic is without asking someone.
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
from hrono.server.ui import guide as guide_ui
from hrono.server.ui import templates

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
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
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


def _said(html: str) -> str:
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def test_every_number_on_the_page_is_the_constant_behind_it(
    browser: Browser, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A number typed into the page is a number that goes stale.

    Every figure the page quotes is moved to a value nobody would type, and
    the page must follow it. A literal left in the template shows up as the
    old figure surviving next to the new one.
    """
    for name, value in {
        "TAU": 0.61,
        "MAX_CAP": 41,
        "MISFIT_THRESHOLD": 0.33,
        "CHURN_THRESHOLD": 77,
        "MISFIT_FACTOR": 3.0,
        "D_MAX": 6,
        "BEST_OF": 11,
        "CAP": 13,
        "MAX_DOCUMENT_SHARE": 0.35,
        "WIDTH": 23,
        "DEFAULT_LEVELS": 8,
    }.items():
        monkeypatch.setattr(guide_ui, name, value)
    monkeypatch.setitem(
        templates.env.globals, "limits", {"section": 7168, "passage": 900}
    )
    browser.sign_in()

    page = _said(browser.guide())

    for shown in (
        "0.61 similar",
        "past 41 sections",
        "over 33% misfits",
        "77 drift points",
        "passes 3 times",
        "up to 6 levels",
        "panel of 11",
        "Up to 13 come back",
        "more than 35%",
        "at most 23 topics",
        "8 by default",
        "~7 KB of one file",
        "~900 B",
    ):
        assert shown in page, shown
    for old in ("0.7 similar", "30 sections", "25%", "10 KB", "800 B"):
        assert old not in page, old


@pytest.mark.parametrize(
    ("method", "path", "body", "least"),
    [
        ("get", "/trees/default/export", None, "reader"),
        ("post", "/trees/default/sync", {}, "writer"),
        ("post", "/sources", {}, "writer"),
        ("patch", "/trees/default/nodes/1", {"title": "x"}, "admin"),
        ("post", "/jobs", {"op": "noop", "scope": {}}, "admin"),
    ],
    ids=["look", "sync", "settings", "edit-a-topic", "single-stage"],
)
def test_the_roles_table_matches_what_the_server_allows(
    browser: Browser, method: str, path: str, body: object, least: str
) -> None:
    """The page says what each account can do; the server is what decides.

    Each row of the table is held to a real request made as each role, so
    loosening or tightening a route fails the page that describes it.
    """
    ranks = ("reader", "writer", "admin")
    for role in ranks:
        answer = browser.client.request(
            method.upper(),
            path,
            json=body,
            headers={"Authorization": f"Bearer {browser.tokens[role]}"},
        )
        allowed = ranks.index(role) >= ranks.index(least)
        assert (answer.status_code != 403) is allowed, (role, answer.text)


def test_the_page_lists_every_account_once_in_order(browser: Browser) -> None:
    browser.sign_in()

    rows = re.findall(
        r'<th scope="row">(\w+)</th><td>', browser.guide().replace("\n", "")
    )

    assert [r for r in rows if r in {"reader", "writer", "admin"}] == [
        "reader",
        "writer",
        "admin",
    ]


def test_the_not_used_words_are_the_glossarys(browser: Browser) -> None:
    """The Guide's list of words not used and GLOSSARY.md's are one list."""
    from tests.server.test_ui_vocabulary import banned_words

    browser.sign_in()

    page = browser.guide()
    block = re.search(r"data-not-used>(.*?)</p>", page, re.S)
    assert block is not None
    named = {w.lower() for w in re.findall(r"<strong>(\w+)</strong>", block[1])}

    assert named == set(banned_words())
