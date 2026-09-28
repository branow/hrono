"""#182 (T51): the dashboard's topic page.

The ordering is the substance here — "worst fit first" is a claim about NULLs
sorting last, which is the opposite of what SQLite does by default.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono import notes, pins
from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.server.app import create_app
from hrono.summarize import briefs

KEY = Fernet.generate_key()
TREE = "default"


class Browser:
    def __init__(self, client: TestClient, token: str, conn: object) -> None:
        self.client = client
        self.token = token
        self.conn = conn

    def sign_in(self) -> None:
        self.client.post("/ui/login", data={"token": self.token})

    def node(self, node_id: int, tree: str = TREE) -> object:
        return self.client.get(f"/ui/trees/{tree}/nodes/{node_id}")


def _section(conn: object, path: str, body: bytes) -> int:
    digest = content_hash(body)
    istore.upsert_content(conn, digest, body)  # type: ignore[arg-type]
    return istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="docs",
        address=Address("git", "ex/docs", path, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[Browser]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    with conn:
        core = _section(
            conn, "docs/sign/core.md", b"<script>alert(1)</script> core\n"
        )
        edge = _section(conn, "docs/sign/edge.md", b"E" * 2000)
        worse = _section(
            conn, "docs/sign/worse.md", b"the worst fitting chunk\n"
        )
        pushed = _section(conn, "docs/sign/pushed.md", b"a forced member\n")
        node = cluster_store.add_leaf_node(
            conn,
            TREE,
            # (section, FORCED, similarity) — the middle field is `forced`,
            # and `attached` is set from it (0009/_insert_member)
            [
                (core, False, None),  # a density core: no score at all
                (edge, False, 0.80),  # attached by proximity
                (worse, False, 0.72),  # attached, and the worst of them
                (pushed, True, None),  # forced: nobody scored it (#113)
            ],
        )
        briefs.upsert(
            conn,
            node,
            "Signing and serialization.\nThe modules that sign payloads.",
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature="sig",
            input_tokens=1,
            output_tokens=1,
        )
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 1, 0, 't')",
            (TREE,),
        )
        parent = int(conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0])
        cluster_store.add_child(
            conn, parent, node, attached=False, similarity=None
        )
        pins.pin(conn, pins.BRIEF, node, reason="renamed by hand")
        notes.add(conn, notes.NODE, node, "watch this one")
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Browser(client, token, conn)
    conn.close()


def _node_id(browser: Browser) -> int:
    return int(
        browser.conn.execute(  # type: ignore[attr-defined]
            "SELECT MIN(id) FROM nodes WHERE level = 0"
        ).fetchone()[0]
    )


def test_the_page_shows_the_brief_and_where_the_topic_sits(
    browser: Browser,
) -> None:
    browser.sign_in()

    page = browser.node(_node_id(browser)).text  # type: ignore[attr-defined]

    assert "Signing and serialization." in page
    assert "level 0" in page
    assert "under <a" in page


def test_members_are_worst_fit_first_with_core_last(
    browser: Browser,
) -> None:
    """NULL means a CONFIDENT placement, so nulls sort LAST.

    SQLite orders NULLs first by default, so this is the opposite of the
    obvious `ORDER BY assignment_similarity` and the whole point of the view.
    """
    browser.sign_in()

    page = browser.node(_node_id(browser)).text  # type: ignore[attr-defined]
    # the path is drawn in two parts — the directory it shares with its topic,
    # then what tells it apart — so the row is rebuilt from both
    order = [
        stem + tail
        for stem, tail in re.findall(
            r'class="path"><span class="dim">([^<]*)</span>([^<]+)</span>', page
        )
    ]

    assert order == [
        "docs/sign/worse.md",  # 0.72, the least likely to belong
        "docs/sign/edge.md",  # 0.80
        # then the unscored, by id: a confident core and a forced placement
        "docs/sign/core.md",
        "docs/sign/pushed.md",
    ]


def test_a_forced_member_is_marked(browser: Browser) -> None:
    # #113: a forced placement is one nobody scored, and it should not read as
    # a confident one.
    browser.sign_in()

    page = browser.node(_node_id(browser)).text  # type: ignore[attr-defined]

    assert "forced" in page


def test_a_score_is_shown_for_an_attached_member(browser: Browser) -> None:
    browser.sign_in()

    assert "0.72" in browser.node(_node_id(browser)).text  # type: ignore[attr-defined]


def test_a_section_preview_is_inline_and_bounded(browser: Browser) -> None:
    # a section is ~10 KB and a topic can hold thirty; the preview keeps the
    # topic on screen.
    browser.sign_in()

    page = browser.node(_node_id(browser)).text  # type: ignore[attr-defined]

    assert "E" * 600 in page  # the preview
    assert "E" * 700 not in page  # and not the whole 2000-byte section
    assert "…" in page


def test_pins_and_notes_are_visible(browser: Browser) -> None:
    browser.sign_in()

    page = browser.node(_node_id(browser)).text  # type: ignore[attr-defined]

    assert "brief" in page  # the pin kind
    assert "watch this one" in page


def test_a_node_from_another_tree_is_a_404(browser: Browser) -> None:
    browser.sign_in()

    assert browser.node(_node_id(browser), tree="other").status_code == 404  # type: ignore[attr-defined]


def test_an_unknown_node_is_a_404(browser: Browser) -> None:
    browser.sign_in()

    assert browser.node(99999).status_code == 404  # type: ignore[attr-defined]


def test_the_page_needs_a_login(browser: Browser) -> None:
    answer = browser.client.get(
        f"/ui/trees/{TREE}/nodes/1", follow_redirects=False
    )

    assert answer.status_code == 303
    assert answer.headers["location"] == "/ui/login"


def test_section_content_is_escaped_not_executed(browser: Browser) -> None:
    """A chunk's body is UNTRUSTED: it came from someone's repository.

    Jinja autoescapes, and this is the assertion that says we rely on it —
    the preview renders a section verbatim, so a `<script>` in a source file
    would otherwise run in the operator's browser with their cookie.
    """
    browser.sign_in()

    page = browser.node(_node_id(browser)).text  # type: ignore[attr-defined]

    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<script>alert(1)</script>" not in page


def test_a_child_topic_is_listed_by_its_name_not_its_number(
    browser: Browser,
) -> None:
    """#197: the topic page listed children as "topic 27", "topic 28".

    Every one of them has a title the map already shows, so navigating the
    tree from here meant navigating by row id.
    """
    browser.sign_in()
    parent = int(
        browser.conn.execute(  # type: ignore[attr-defined]
            "SELECT MAX(id) FROM nodes"
        ).fetchone()[0]
    )

    page = browser.node(parent).text  # type: ignore[attr-defined]

    assert "Signing and serialization." in page


def test_a_long_title_is_cut_at_a_word_and_says_so(browser: Browser) -> None:
    """A heading that stops mid-clause reads as a rendering fault."""
    long_brief = (
        "This group covers the parts of the system that decide which chunks "
        "belong together and which do not, at some length."
    )
    node = _node_id(browser)
    with browser.conn:  # type: ignore[union-attr]
        browser.conn.execute(  # type: ignore[attr-defined]
            "UPDATE briefs SET text = ? WHERE node_id = ?", (long_brief, node)
        )
    browser.sign_in()

    page = browser.node(node).text  # type: ignore[attr-defined]

    # the NAME, not the page: the chunk previews carry their own ellipsis, so
    # asking whether the page contains one proves nothing about the title.
    # The h1 is the path the topic's chunks live under (#198); the brief's
    # first line is the secondary identity under it.
    said = re.search(r'<p class="said">(.*?)</p>', page, re.S)
    assert said is not None
    title = said.group(1).strip()
    assert title.endswith("…")  # an ellipsis, not a hard stop
    # and the cut respects a word: the character AFTER the stem, in the
    # original, is a space. A hard 80-character cut lands inside "together".
    stem = title.removesuffix("…")
    assert long_brief.startswith(stem)
    assert long_brief[len(stem)] == " "
    assert len(title) < len(long_brief)
