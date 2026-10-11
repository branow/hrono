"""Rename, brief, notes and hand-back from the page.

Every assertion is made against the STORE the operation writes, not against
the page that reports it. A UI that wrote `nodes.title` directly would render
a correct page and lose the name on the next regeneration — which is the whole
reason `edits.rename` pins the brief.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono import edits, notes, pins
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
        # happens to be writing when a poll lands.
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
    a silent revert waiting for the next regeneration."""
    browser.sign_in()

    browser.post("rename", title="Named by hand")

    assert browser.pins() == {"brief": "renamed by hand"}


def test_a_hand_written_brief_reaches_recall(browser: Browser) -> None:
    """Not just the page: the brief is what recall answers from."""
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


@pytest.mark.parametrize("role", ["reader", "writer"])
def test_a_reader_or_a_writer_sees_no_forms(
    browser: Browser, role: str
) -> None:
    # the API's floor for these is ADMIN; the page may not be a softer door
    browser.sign_in(role)

    page = browser.page()

    # the drawer AND the thing it holds: a label can be renamed, a form action
    # is what the control actually is
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


def test_a_rewritten_brief_shows_the_old_text_and_what_changed(
    browser: Browser,
) -> None:
    """The page that wrote a brief can show what it replaced."""
    browser.sign_in()
    assert "Previous versions" not in browser.page()

    browser.post("brief", text="What an operator actually knows.")
    page = browser.page()

    assert "Previous versions" in page
    assert "replaced by a hand rewrite" in page
    assert (
        '<span class="diff-del" data-mark="-">The summary the model wrote.'
        "</span>"
    ) in page
    assert (
        '<span class="diff-add" data-mark="+">What an operator actually '
        "knows.</span>"
    ) in page


def test_two_hand_rewrites_in_a_row_never_read_by_by_hand(
    browser: Browser,
) -> None:
    browser.sign_in()

    browser.post("brief", text="First rewrite.")
    browser.post("brief", text="Second rewrite.")
    page = browser.page()

    assert "by by" not in page
    assert page.count("by hand (") == 1
    assert "replaced by a hand rewrite (" in page


def test_a_regeneration_replaced_version_says_so(browser: Browser) -> None:
    browser.sign_in()

    with browser.conn:  # type: ignore[attr-defined]
        briefs.upsert(
            browser.conn,  # type: ignore[arg-type]
            browser.node,
            "A regenerated summary.",
            model_name="m2",
            prompt_name="brief",
            prompt_hash="h",
            member_signature="sig",
            input_tokens=1,
            output_tokens=1,
        )
    page = browser.page()

    assert "by m (" in page
    assert "replaced by a regeneration (" in page
    assert "replaced by a hand rewrite" not in page


def _log(browser: Browser) -> list[tuple[str, str | None, str]]:
    return [
        (r["kind"], r["before"], r["who"])
        for r in browser.conn.execute(  # type: ignore[attr-defined]
            "SELECT kind, before, who FROM edit_log WHERE node_id = ? "
            "ORDER BY id",
            (browser.node,),
        )
    ]


def _closed(browser: Browser) -> list[str | None]:
    return [
        r["closed"]
        for r in browser.conn.execute(  # type: ignore[attr-defined]
            "SELECT closed FROM edit_log WHERE node_id = ? ORDER BY id",
            (browser.node,),
        )
    ]


def _latest(browser: Browser) -> str:
    return str(
        browser.conn.execute(  # type: ignore[attr-defined]
            "SELECT MAX(id) FROM edit_log WHERE node_id = ?", (browser.node,)
        ).fetchone()[0]
    )


def _brief(browser: Browser) -> str:
    return str(briefs.get(browser.conn, browser.node)["text"])  # type: ignore[arg-type,index]


def _offered(browser: Browser) -> str:
    return edits.latest_edit(browser.conn, browser.node)["kind"]  # type: ignore[arg-type,index]


def test_each_manual_edit_records_what_it_replaced(browser: Browser) -> None:
    browser.sign_in()

    browser.post("rename", title="First name")
    browser.post("rename", title="Second name")
    # the newest edit is the one offered for undo
    assert _offered(browser) == "rename"
    browser.post("brief", text="Hand text.")
    assert _offered(browser) == "brief"
    browser.post("note", text="A remark")

    assert _log(browser) == [
        ("rename", None, "admin"),
        ("rename", "First name", "admin"),
        ("brief", "The summary the model wrote.", "admin"),
        ("note", None, "admin"),
    ]


@pytest.mark.parametrize(
    ("route", "field", "same"),
    [
        ("rename", "title", "Same name"),
        ("brief", "text", "The summary the model wrote."),
    ],
    ids=["rename", "brief"],
)
def test_a_same_value_edit_offers_no_undo(
    browser: Browser, route: str, field: str, same: str
) -> None:
    browser.sign_in()
    with browser.conn:  # type: ignore[attr-defined]
        browser.conn.execute(  # type: ignore[attr-defined]
            "UPDATE nodes SET title = ? WHERE id = ?",
            ("Same name", browser.node),
        )

    browser.post(route, **{field: same})

    assert _log(browser) == []
    assert "Undo" not in browser.page()
    assert browser.pins()


def test_handing_back_clears_the_undo_so_a_regeneration_stands(
    browser: Browser,
) -> None:
    browser.sign_in()
    browser.post("brief", text="A hand rewrite.")
    assert "Undo brief rewrite" in browser.page()

    browser.post("release")
    with browser.conn:  # type: ignore[attr-defined]
        briefs.upsert(
            browser.conn,  # type: ignore[arg-type]
            browser.node,
            "Regenerated after the hand-back.",
            model_name="m2",
            prompt_name="brief",
            prompt_hash="h",
            member_signature="sig",
            input_tokens=1,
            output_tokens=1,
        )

    assert [r[0] for r in _log(browser)] == ["brief"]
    assert _closed(browser) == ["released"]
    assert "Undo" not in browser.page()
    assert browser.pins() == {}
    assert _brief(browser) == "Regenerated after the hand-back."


def test_an_undone_rewrite_names_the_original_author(
    browser: Browser,
) -> None:
    browser.sign_in()
    browser.post("brief", text="A wrong rewrite.")
    assert "hand-edited" in browser.page()

    browser.post("undo", edit=_latest(browser), confirm="yes")
    row = briefs.get(browser.conn, browser.node)  # type: ignore[arg-type]

    assert row["model_name"] == "m"  # type: ignore[index]
    assert (row["prompt_name"], row["prompt_hash"]) == ("brief", "h")  # type: ignore[index]
    assert (row["input_tokens"], row["output_tokens"]) == (1, 1)  # type: ignore[index]
    assert "hand-edited" not in browser.page()
    assert "brief" in browser.pins()


def _record_of(conn: object, node: int) -> dict[str, object]:
    row = conn.execute(  # type: ignore[attr-defined]
        "SELECT * FROM briefs WHERE node_id = ?", (node,)
    ).fetchone()
    return dict(row)


def test_an_undone_rewrite_keeps_the_briefs_whole_record(
    browser: Browser,
) -> None:
    browser.sign_in()
    conn = browser.conn  # type: ignore[attr-defined]
    with conn:
        briefs.upsert(
            conn,
            browser.node,
            "The summary the model wrote.",
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature=briefs.member_signature(conn, browser.node),
            input_tokens=1,
            output_tokens=1,
            model_fingerprint="fp",
            unfaithful='["x"]',
            flagged="shape",
            members='["git://ex/docs/a.md"]',
            source_model="cm",
        )
    before = _record_of(conn, browser.node)

    browser.post("brief", text="A wrong rewrite.")
    browser.post("undo", edit=_latest(browser), confirm="yes")
    browser.post("release")
    after = _record_of(conn, browser.node)

    for key in (
        "members",
        "source_model",
        "model_fingerprint",
        "member_signature",
        "unfaithful",
        "flagged",
    ):
        assert after[key] == before[key], key


def test_a_handed_back_undone_rewrite_stays_fresh_with_its_references(
    browser: Browser,
) -> None:
    browser.sign_in()
    conn = browser.conn  # type: ignore[attr-defined]
    with conn:
        briefs.upsert(
            conn,
            browser.node,
            "The docs describe how the service is configured, started and "
            "stopped, and which settings an operator changes most often.",
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature=briefs.member_signature(conn, browser.node),
            input_tokens=1,
            output_tokens=1,
            members='["git://ex/docs/a.md"]',
            source_model="cm",
        )

    browser.post("brief", text="A wrong rewrite.")
    browser.post("undo", edit=_latest(browser), confirm="yes")
    browser.post("release")

    assert _record_of(conn, browser.node)["members"] == '["git://ex/docs/a.md"]'
    assert briefs.stale_or_missing(conn, TREE, 0, "h", "m") == ()


def test_an_undone_rewrite_of_an_unknown_record_is_rebriefed(
    browser: Browser,
) -> None:
    browser.sign_in()
    conn = browser.conn  # type: ignore[attr-defined]
    long = (
        "The docs describe how the service is configured, started and "
        "stopped, and which settings an operator changes most often."
    )
    with conn:
        briefs.upsert(
            conn,
            browser.node,
            long,
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature=briefs.member_signature(conn, browser.node),
            input_tokens=1,
            output_tokens=1,
        )
    browser.post("brief", text="A rewrite over a brief with a stale record.")
    with conn:
        conn.execute(
            "UPDATE brief_versions SET member_signature = 'old' "
            "WHERE node_id = ?",
            (browser.node,),
        )

    browser.post("undo", edit=_latest(browser), confirm="yes")
    browser.post("release")

    assert _brief(browser) == long
    assert briefs.stale_or_missing(conn, TREE, 0, "h", "m") == (browser.node,)


def test_a_stale_undo_never_undoes_a_later_edit(browser: Browser) -> None:
    browser.sign_in()
    browser.post("rename", title="Renamed")
    stale = _latest(browser)
    browser.post("undo", edit=stale, confirm="yes")
    browser.post("brief", text="A later rewrite of the brief.")

    answer = browser.post("undo", edit=stale, confirm="yes")

    assert "no longer the topic" in answer.text
    assert _brief(browser) == "A later rewrite of the brief."
    assert _latest(browser) != stale


def test_the_edits_list_shows_each_edit_with_who_and_when(
    browser: Browser,
) -> None:
    create_user(browser.conn, "bea", "admin")  # type: ignore[arg-type]
    browser.sign_in()
    browser.post("rename", title="Named")
    browser.post("note", text="A remark")
    browser.client.post("/ui/logout")
    browser.client.post(
        "/ui/login",
        data={"token": create_user(browser.conn, "cy", "admin")[1]},  # type: ignore[arg-type]
    )
    browser.post("brief", text="Cy's rewrite.")
    browser.sign_in("reader")

    page = browser.page()

    assert "<h2>Edits" in page
    items = re.findall(r"<li>(.*?)</li>", page.split("<h2>Edits")[1])
    assert [re.sub(r"<[^>]+>", "", i) for i in items[:3]] == [
        f"Brief rewrite by cy, {_stamp(browser, 'cy')}",
        f"Note by admin, {_stamp(browser, 'admin', 'note')}",
        f"Rename by admin, {_stamp(browser, 'admin', 'rename')}",
    ]
    assert "Undo" not in page


def _stamp(browser: Browser, who: str, kind: str = "brief") -> str:
    row = browser.conn.execute(  # type: ignore[attr-defined]
        "SELECT made_at FROM edit_log WHERE who = ? AND kind = ?", (who, kind)
    ).fetchone()
    return str(row["made_at"]).replace("T", " ")[:16]


def test_a_topic_with_no_edits_has_no_edits_heading(browser: Browser) -> None:
    browser.sign_in("reader")

    assert "<h2>Edits" not in browser.page()


def test_an_undone_edit_stays_listed_and_is_tagged(browser: Browser) -> None:
    browser.sign_in()
    browser.post("rename", title="Named")
    browser.post("undo", edit=_latest(browser), confirm="yes")

    page = browser.page()

    assert "undone</span>" in page
    assert len(_log(browser)) == 1
    assert "Undo rename" not in page


def test_a_hand_back_after_an_undo_keeps_the_edit_undone(
    browser: Browser,
) -> None:
    browser.sign_in()
    browser.post("rename", title="Named")
    browser.post("undo", edit=_latest(browser), confirm="yes")

    browser.post("release")

    assert _closed(browser) == ["undone"]
    assert "undone</span>" in browser.page()


def test_the_edits_list_caps_at_ten_and_counts_the_rest(
    browser: Browser,
) -> None:
    browser.sign_in()
    for n in range(13):
        browser.post("note", text=f"remark {n}")

    section = browser.page().split("<h2>Edits")[1].split("</section>")[0]

    assert section.count("<li>") == 10
    assert "and 3 older" in section


def test_a_refused_edit_records_nothing(browser: Browser) -> None:
    browser.sign_in()

    browser.post("rename", title="")
    browser.post("brief", text="")

    assert _log(browser) == []


def test_undo_puts_the_old_name_back(browser: Browser) -> None:
    browser.sign_in()
    browser.post("rename", title="Mistake")

    page = browser.page()
    assert "Undo rename" in page
    assert "The name is removed" in page
    answer = browser.post("undo", edit=_latest(browser), confirm="yes")

    assert "undone: rename" in answer.text
    assert browser.title() is None
    assert "Undo rename" not in browser.page()
    assert browser.pins() == {"brief": "renamed by hand"}


def test_undo_restores_a_named_topics_earlier_name(browser: Browser) -> None:
    browser.sign_in()
    browser.post("rename", title="Good")
    browser.post("rename", title="Bad")

    assert "The name goes back to &#34;Good&#34;" in browser.page()
    browser.post("undo", edit=_latest(browser), confirm="yes")

    assert browser.title() == "Good"


def test_undo_restores_the_old_brief_for_recall_too(browser: Browser) -> None:
    browser.sign_in()
    browser.post("brief", text="A wrong rewrite.")

    browser.post("undo", edit=_latest(browser), confirm="yes")

    assert _brief(browser) == "The summary the model wrote."
    assert "The summary the model wrote." in _brief_passage_text(browser)
    assert "wrong rewrite" not in _brief_passage_text(browser)
    assert "brief" in browser.pins()


def test_undo_removes_the_note(browser: Browser) -> None:
    browser.sign_in()
    browser.post("note", text="Added by mistake")

    browser.post("undo", edit=_latest(browser), confirm="yes")

    assert notes.get(browser.conn, notes.NODE, browser.node) == ()  # type: ignore[arg-type]
    assert browser.pins() == {}


def test_undo_twice_does_not_reach_an_older_edit(browser: Browser) -> None:
    browser.sign_in()
    browser.post("rename", title="Older")
    browser.post("rename", title="Newer")
    stale = _latest(browser)

    browser.post("undo", edit=stale, confirm="yes")
    answer = browser.post("undo", edit=stale, confirm="yes")

    assert "no longer the topic" in answer.text
    assert browser.title() == "Older"
    assert "Undo rename" not in browser.page()
    assert _closed(browser) == [None, "undone"]


def test_undo_of_a_shown_edit_is_refused_once_another_landed(
    browser: Browser,
) -> None:
    browser.sign_in()
    browser.post("rename", title="Shown")
    shown = _latest(browser)
    browser.post("note", text="Landed after the page was drawn")

    answer = browser.post("undo", edit=shown, confirm="yes")

    assert "no longer the topic" in answer.text
    assert browser.title() == "Shown"


def test_undo_needs_the_box_ticked(browser: Browser) -> None:
    browser.sign_in()
    browser.post("rename", title="Kept")

    answer = browser.post("undo", edit=_latest(browser))

    assert "tick the box" in answer.text
    assert browser.title() == "Kept"


def test_undo_of_a_rewrite_with_no_earlier_brief_is_not_offered(
    browser: Browser,
) -> None:
    browser.sign_in()
    with browser.conn:  # type: ignore[attr-defined]
        browser.conn.execute(  # type: ignore[attr-defined]
            "DELETE FROM briefs WHERE node_id = ?", (browser.node,)
        )
    browser.post("brief", text="First ever brief.")

    assert "Undo brief rewrite" not in browser.page()


def test_a_readers_and_a_writers_undo_is_refused(browser: Browser) -> None:
    browser.sign_in()
    browser.post("rename", title="Kept")
    edit = _latest(browser)
    for role in ("reader", "writer"):
        browser.sign_in(role)

        answer = browser.post("undo", edit=edit, confirm="yes")

        assert answer.status_code == 403
        assert browser.title() == "Kept"
        assert "Undo rename" not in browser.page()


def _kinds(old: str, new: str) -> list[str]:
    from hrono.server.ui.nodes import _diff

    return [row["kind"] for row in _diff(old, new)]


def test_a_diff_marks_a_gap_before_a_change_that_is_not_the_first_line() -> (
    None
):
    old = "\n".join(f"l{n}" for n in range(10))
    new = old.replace("l5", "L5")

    assert _kinds(old, new) == ["gap", "same", "del", "add", "same", "gap"]


def test_a_diff_marks_a_gap_between_two_distant_changes() -> None:
    old = "\n".join(f"l{n}" for n in range(20))
    new = old.replace("l0", "L0").replace("l19", "L19")

    kinds = _kinds(old, new)
    assert kinds == ["del", "add", "same", "gap", "same", "del", "add"]
