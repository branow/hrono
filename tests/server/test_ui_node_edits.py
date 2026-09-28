"""#188 (T56, edit half): rename, brief, notes and hand-back from the page.

Every assertion is made against the STORE the operation writes, not against
the page that reports it. A UI that wrote `nodes.title` directly would render
a correct page and lose the name on the next regeneration — which is the whole
reason `edits.rename` pins the brief (#156).
"""

from __future__ import annotations

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
    def __init__(self, client: TestClient, tokens: dict, conn: object) -> None:
        self.client = client
        self.tokens = tokens
        self.conn = conn
        self.node = 0

    def sign_in(self, role: str = "admin") -> None:
        self.client.post("/ui/login", data={"token": self.tokens[role]})

    def page(self) -> str:
        return self.client.get(f"/ui/trees/{TREE}/nodes/{self.node}").text

    def post(self, what: str, **fields: str):  # type: ignore[no-untyped-def]
        return self.client.post(
            f"/ui/trees/{TREE}/nodes/{self.node}/{what}", data=fields
        )

    def title(self) -> str | None:
        row = self.conn.execute(  # type: ignore[attr-defined]
            "SELECT title FROM nodes WHERE id = ?", (self.node,)
        ).fetchone()
        return row["title"]

    def pins(self) -> dict[str, str | None]:
        return pins.reasons(self.conn, self.node)  # type: ignore[arg-type]


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[Browser]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    with conn:
        body = b"a chunk of the corpus\n"
        digest = content_hash(body)
        istore.upsert_content(conn, digest, body)
        section = istore.insert_section(
            conn,
            source="docs",
            address=Address("git", "ex/docs", "a.md", "v1"),
            start=0,
            end=len(body),
            content_hash=digest,
            ordinal=0,
        )
        node = cluster_store.add_leaf_node(conn, TREE, [(section, False, None)])
        briefs.upsert(
            conn,
            node,
            "The summary the model wrote.",
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature="sig",
            input_tokens=1,
            output_tokens=1,
        )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        # The worker polls the SAME adopted connection this fixture writes
        # through. Two threads on one sqlite connection interleave
        # transactions, which is an intermittent failure in whichever test
        # happens to be writing when a poll lands (#194).
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        browser = Browser(client, tokens, conn)
        browser.node = node
        yield browser
    conn.close()


def test_a_rename_lands_in_the_store_and_on_the_page(
    browser: Browser,
) -> None:
    browser.sign_in()

    answer = browser.post("rename", title="Signing and serialization")

    assert answer.status_code == 200  # followed the redirect
    assert browser.title() == "Signing and serialization"
    assert "Signing and serialization" in browser.page()


def test_a_rename_pins_the_brief_so_it_cannot_be_re_derived(
    browser: Browser,
) -> None:
    """The name is derived from the brief, so a rename that does not pin it is
    a silent revert waiting for the next regeneration (#156)."""
    browser.sign_in()

    browser.post("rename", title="Named by hand")

    assert browser.pins() == {"brief": "renamed by hand"}


def test_a_hand_written_brief_reaches_recall(browser: Browser) -> None:
    """Not just the page: the brief is what recall answers from (#071/#125)."""
    browser.sign_in()

    browser.post("brief", text="What an operator actually knows about this.")

    stored = _brief_passage_text(browser)
    assert "What an operator actually knows" in stored
    assert "What an operator actually knows" in browser.page()


def _brief_passage_text(browser: Browser) -> str:
    """The brief as RECALL would read it: the node:// passage bodies."""
    rows = browser.conn.execute(  # type: ignore[attr-defined]
        "SELECT c.body AS body FROM passages p "
        "JOIN contents c ON c.content_hash = p.content_hash "
        "WHERE p.source = ? ORDER BY p.id",
        (f"node-{browser.node}",),
    ).fetchall()
    return "".join(bytes(row["body"]).decode() for row in rows)


def test_a_note_is_added_and_shown(browser: Browser) -> None:
    browser.sign_in()

    browser.post("note", text="this one drifts every sync")

    assert notes.get(browser.conn, notes.NODE, browser.node)  # type: ignore[arg-type]
    assert "this one drifts every sync" in browser.page()


def test_handing_back_releases_every_pin(browser: Browser) -> None:
    browser.sign_in()
    browser.post("rename", title="Held by hand")
    assert browser.pins()

    answer = browser.post("release")

    assert browser.pins() == {}
    assert "2 pins released" in answer.text or "1 pins released" in answer.text


def test_a_blank_title_is_refused_and_said_so(browser: Browser) -> None:
    browser.sign_in()

    answer = browser.post("rename", title="")

    assert browser.title() is None
    assert "title" in answer.text
    assert "at least 1 character" in answer.text


def test_a_reader_sees_no_forms(browser: Browser) -> None:
    browser.sign_in("reader")

    page = browser.page()

    # the drawer AND the thing it holds: a label can be renamed, a form action
    # is what the control actually is
    assert "Correct this topic by hand" not in page
    assert f"/nodes/{browser.node}/rename" not in page
    assert f"/nodes/{browser.node}/dissolve" not in page


def test_a_writer_sees_no_forms_either(browser: Browser) -> None:
    # the API's floor for these is ADMIN; the page may not be a softer door
    browser.sign_in("writer")

    page = browser.page()

    assert "Correct this topic by hand" not in page
    assert f"/nodes/{browser.node}/rename" not in page
    assert f"/nodes/{browser.node}/dissolve" not in page


def test_a_writers_post_is_refused(browser: Browser) -> None:
    browser.sign_in("writer")

    answer = browser.post("rename", title="by someone without the role")

    assert answer.status_code == 403
    assert browser.title() is None


def test_a_signed_out_post_is_refused(browser: Browser) -> None:
    answer = browser.client.post(
        f"/ui/trees/{TREE}/nodes/{browser.node}/rename",
        data={"title": "nobody"},
        follow_redirects=False,
    )

    assert answer.status_code in (303, 401)
    assert browser.title() is None


def test_a_write_redirects_so_a_refresh_repeats_nothing(
    browser: Browser,
) -> None:
    browser.sign_in()

    answer = browser.client.post(
        f"/ui/trees/{TREE}/nodes/{browser.node}/note",
        data={"text": "once"},
        follow_redirects=False,
    )
    browser.client.get(answer.headers["location"])
    browser.client.get(answer.headers["location"])

    assert len(notes.get(browser.conn, notes.NODE, browser.node)) == 1  # type: ignore[arg-type]


def test_a_title_cannot_break_out_of_its_input(browser: Browser) -> None:
    """A topic name is operator input reflected into an ATTRIBUTE.

    The rename form pre-fills the current name, which is the one place on this
    page where untrusted text lands inside quotes rather than between tags.
    """
    browser.sign_in()

    browser.post("rename", title='" autofocus onfocus="alert(1)')

    page = browser.page()
    assert 'onfocus="alert(1)"' not in page
    assert "&#34; autofocus onfocus=&#34;alert(1)" in page


def test_the_outcome_message_is_not_a_reflection_hole(
    browser: Browser,
) -> None:
    # `?error=` and `?done=` are whatever the URL says, and the page prints
    # them: the classic reflected spot, and the one a redirect makes easy
    browser.sign_in()

    page = browser.client.get(
        f"/ui/trees/{TREE}/nodes/{browser.node}?error=<script>alert(1)</script>"
    ).text

    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page


def test_a_note_is_shown_as_text_not_markup(browser: Browser) -> None:
    browser.sign_in()

    browser.post("note", text="<img src=x onerror=alert(1)>")

    assert "<img src=x" not in browser.page()
