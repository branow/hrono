"""The dashboard's topic page.

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
from hrono.ingest import Unit
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.split_op import store_unit
from hrono.server.app import create_app
from hrono.summarize import briefs
from hrono.summarize import store as condensations

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
        edge = _section(conn, "docs/sign/edge.md", b"E" * 12000)
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
                (pushed, True, None),  # forced: nobody scored it
            ],
        )
        briefs.upsert(
            conn,
            node,
            "Signing and serialization.\nThe modules that sign payloads.",
            model_name="scribe-9",
            prompt_name="brief",
            prompt_hash="pr00mpth4sh",
            member_signature="sig-written",
            input_tokens=1234,
            output_tokens=56,
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
        # The worker polls the SAME adopted connection this fixture and its
        # tests write through. Two threads on one sqlite connection interleave
        # transactions, which is an intermittent failure in whichever test
        # happens to be writing when a poll lands.
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
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
    # the parent is named ONCE, in the panel beside the brief, not also as
    # a chip under the title repeating a path the h1 already shows
    assert "<dt>Parent</dt>" in page


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
    # a forced placement is one nobody scored, and it should not read as
    # a confident one; an attached member shows its score
    assert "forced" in page
    assert "0.72" in page


def test_a_section_is_shown_WHOLE(browser: Browser) -> None:
    """No cut at 4,000 characters with a count of what is held back. The
    one thing a reader opens a section FOR is the part such a cut would
    remove — and a section is already the readable unit the splitter
    chose, inside a `<details>` nobody opens by accident."""
    browser.sign_in()

    page = browser.node(_node_id(browser)).text  # type: ignore[attr-defined]

    assert "E" * 12000 in page  # the whole 12,000-byte section
    assert "12,000 characters" in page
    assert "Showing the first" not in page
    # and a short one still says how big it is, so the two read the same
    assert "31 characters" in page
    # whole, but folded behind "Source" until asked for: the summary is what
    # an open section leads with
    source = page.index('<summary class="twisty">Source')
    assert page.index("E" * 12000) > source
    assert page.rfind('<details class="section-more">', 0, source) > 0


def test_pins_say_what_they_hold_and_why(browser: Browser) -> None:
    """A pin with no reason is a mystery someone resolves by deleting it."""
    browser.sign_in()

    page = browser.node(_node_id(browser)).text  # type: ignore[attr-defined]

    assert "brief written by hand" in page  # what is held, in plain words
    assert "renamed by hand" in page  # and the why the pin recorded
    assert "watch this one" in page  # the note, in full
    assert "held by hand" in page  # and the head says it is held at all


def test_an_unpinned_topic_shows_no_pins_row(browser: Browser) -> None:
    """Nothing pinned is the normal case, and a row saying so is noise."""
    browser.sign_in()
    node = _node_id(browser)
    with browser.conn:  # type: ignore[union-attr]
        pins.unpin_all(browser.conn, node)  # type: ignore[arg-type]

    page = browser.node(node).text  # type: ignore[attr-defined]

    assert "<dt>Parent</dt>" in page
    assert "<dt>Pinned" not in page
    assert "held by hand" not in page


def test_the_page_shows_who_wrote_the_brief(browser: Browser) -> None:
    """An admin sees everything about a brief on its page.

    The provenance columns are the whole incremental mechanism — an operator
    looking at a brief they distrust wants the model that wrote it, what it
    cost, and whether the members it was written over are still its members.
    """
    browser.sign_in()

    page = browser.node(_node_id(browser)).text  # type: ignore[attr-defined]

    assert "scribe-9" in page  # the model that wrote it
    assert "pr00mpth4sh" in page  # the prompt template it was written from
    assert "1,234 in, 56 out" in page  # what it cost
    assert "sig-written" in page  # the member set it was written over
    # which is NOT the member set this topic now holds
    assert "changed since" in page


def test_a_brief_still_over_its_own_members_says_so(browser: Browser) -> None:
    """The other half: the comparison is real, not a constant.

    The signature is re-derived from the topic's CONTENT, so writing the
    brief's stored signature to what the topic actually holds is the only way
    to reach this state — and the page has to change its answer.
    """
    node = _node_id(browser)
    with browser.conn:  # type: ignore[union-attr]
        browser.conn.execute(  # type: ignore[attr-defined]
            "UPDATE briefs SET member_signature = ? WHERE node_id = ?",
            (briefs.member_signature(browser.conn, node), node),  # type: ignore[arg-type]
        )
    browser.sign_in()

    page = browser.node(node).text  # type: ignore[attr-defined]

    assert "changed since" not in page
    assert "unchanged" in page


@pytest.mark.parametrize("where", ["another-tree", "unknown"])
def test_a_node_not_in_this_tree_is_a_404(browser: Browser, where: str) -> None:
    browser.sign_in()

    if where == "another-tree":
        answer = browser.node(_node_id(browser), tree="other")  # type: ignore[attr-defined]
    else:
        answer = browser.node(99999)  # type: ignore[attr-defined]

    assert answer.status_code == 404


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
    """Children are not listed as "topic 27", "topic 28".

    Every one of them has a title the map already shows, so listing ids would
    make navigating the tree from here navigating by row id.
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
        "The parts of the system that decide which chunks belong together and "
        "which do not, at some length."
    )
    node = _node_id(browser)
    parent = int(
        browser.conn.execute(  # type: ignore[attr-defined]
            "SELECT MAX(id) FROM nodes WHERE level = 1"
        ).fetchone()[0]
    )
    with browser.conn:  # type: ignore[union-attr]
        # the PARENT's brief: a topic is offered by the first line of its own
        # brief in the picker that moves this one under it
        briefs.upsert(
            browser.conn,  # type: ignore[arg-type]
            parent,
            long_brief,
            model_name="scribe-9",
            prompt_name="brief-upper",
            prompt_hash="h",
            member_signature="s",
            input_tokens=1,
            output_tokens=1,
        )
    browser.sign_in()

    page = browser.node(node).text  # type: ignore[attr-defined]

    # the NAME, not the page: the section previews carry their own ellipsis,
    # so asking whether the page contains one proves nothing about the title.
    # The brief's first line is the name a topic is OFFERED under — in the
    # move and merge pickers, and in the map's tooltip. It is not printed
    # under the h1: the whole brief is on this page, so a cut copy of its
    # opening clause above it would say the same thing twice.
    offered = re.findall(r'<span class="who-holds">(.*?)</span>', page, re.S)
    assert offered, "the name is still offered where a topic is chosen"
    title = next(name.strip() for name in offered if name.strip().endswith("…"))
    # and the cut respects a word: the character AFTER the stem, in the
    # original, is a space. A hard 80-character cut lands inside "together".
    stem = title.removesuffix("…")
    assert long_brief.startswith(stem)
    assert long_brief[len(stem)] == " "
    assert len(title) < len(long_brief)


def test_a_section_shows_the_condensation_it_was_summarised_through(
    browser: Browser,
) -> None:
    """The middle of the pipeline is visible.

    hrono condenses each section, then writes the topic's brief FROM those
    condensations. A page showing only the brief and the raw file would hide
    the layer between, which is the layer the brief was actually made of.
    """
    node = _node_id(browser)
    with browser.conn:  # type: ignore[union-attr]
        digest = browser.conn.execute(  # type: ignore[attr-defined]
            "SELECT s.content_hash FROM node_members m "
            "JOIN sections s ON s.id = m.section_id WHERE m.node_id = ? "
            "ORDER BY s.id LIMIT 1",
            (node,),
        ).fetchone()[0]
        condensations.upsert(
            browser.conn,  # type: ignore[arg-type]
            digest,
            "scribe-9",
            "**Signing**\n\nGOTCHA: the signer trusts its own clock.\n",
            10,
            20,
        )
    browser.sign_in()

    page = browser.node(node).text  # type: ignore[attr-defined]

    assert "condensation" in page
    assert "scribe-9" in page  # which model wrote it
    assert "the signer trusts its own clock" in page


def test_a_gotcha_is_shown_ONCE(browser: Browser) -> None:
    """The GOTCHA lines are not lifted out and printed as warnings ABOVE the
    condensation, which opens with those same lines: that says each hazard
    twice and puts the duplicate first, so the reader meets the ending before
    the beginning."""
    node = _node_id(browser)
    with browser.conn:  # type: ignore[union-attr]
        digest = browser.conn.execute(  # type: ignore[attr-defined]
            "SELECT s.content_hash FROM node_members m "
            "JOIN sections s ON s.id = m.section_id WHERE m.node_id = ? "
            "ORDER BY s.id LIMIT 1",
            (node,),
        ).fetchone()[0]
        condensations.upsert(
            browser.conn,  # type: ignore[arg-type]
            digest,
            "scribe-9",
            "Body.\n\n**GOTCHA: deletes silently.**\n\nMore body.\n",
            10,
            20,
        )
    browser.sign_in()

    page = browser.node(node).text  # type: ignore[attr-defined]

    # once in the rendered markdown and once in the raw view the toggle
    # switches to — never a third time as a lifted-out warning above both
    assert page.count("deletes silently") == 2
    assert 'class="callout warn' not in page
    assert "Body." in page and "More body." in page  # and all of it is there


def test_a_section_not_condensed_yet_says_so(browser: Browser) -> None:
    """On a part-built tree this is the common case, and a blank panel reads
    as a bug rather than as a stage that has not run."""
    browser.sign_in()

    page = browser.node(_node_id(browser)).text  # type: ignore[attr-defined]

    assert "Not condensed yet" in page


def test_a_reply_that_is_not_a_brief_does_not_stand(browser: Browser) -> None:
    # a stored brief that is the model talking back must not read "stands"
    node = _node_id(browser)
    with browser.conn:  # type: ignore[union-attr]
        briefs.upsert(
            browser.conn,  # type: ignore[arg-type]
            node,
            "There's no task here — your message is just system context. "
            "Paste the briefs and I'll merge them.",
            model_name="scribe-9",
            prompt_name="brief",
            prompt_hash="pr00mpth4sh",
            member_signature="sig-written",
            input_tokens=1,
            output_tokens=1,
        )
    browser.sign_in()

    page = browser.node(node).text  # type: ignore[attr-defined]

    assert ">not a brief</span>" in page
    assert "the next run rewrites it" in page
    assert "talks-to-the-caller" in page
    assert '<span class="chip ok">stands</span>' not in page


def _topic_over(browser: Browser, section_ids: list[int]) -> int:
    with browser.conn:  # type: ignore[union-attr]
        return cluster_store.add_leaf_node(
            browser.conn,  # type: ignore[arg-type]
            TREE,
            [(sid, False, 0.5 + i / 1000) for i, sid in enumerate(section_ids)],
        )


def _ingest_file(browser: Browser, path: str, raw: bytes) -> list[int]:
    """Split a file the way ingest does, so byte ranges are production's."""
    with browser.conn:  # type: ignore[union-attr]
        stored = store_unit(
            browser.conn,  # type: ignore[arg-type]
            Unit(path=path, body=raw, version="v1"),
            "docs",
            "git",
            "ex/docs",
            "v1",
        )
    return [sid for sid, _, _ in stored]


def _guide_text() -> bytes:
    return b"".join(
        f"## Part {n}\n".encode() + b"line of prose here\n" * 300
        for n in range(1, 6)
    )


def test_the_root_is_not_flagged_and_an_orphan_is(browser: Browser) -> None:
    browser.sign_in()
    with browser.conn:  # type: ignore[union-attr]
        browser.conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 0, 0, 't')",
            (TREE,),
        )
        orphan = int(
            browser.conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0]  # type: ignore[attr-defined]
        )
    root = int(
        browser.conn.execute(  # type: ignore[attr-defined]
            "SELECT MAX(id) FROM nodes WHERE level = 1"
        ).fetchone()[0]
    )

    top = browser.node(root).text  # type: ignore[attr-defined]
    lost = browser.node(orphan).text  # type: ignore[attr-defined]

    assert "nothing points at this topic" not in top
    assert "this is the root" in top
    assert "nothing points at this topic" in lost
    assert "this is the root" not in lost


def test_the_breadcrumb_runs_from_the_root_down(browser: Browser) -> None:
    with browser.conn:  # type: ignore[union-attr]
        browser.conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 2, 0, 't')",
            (TREE,),
        )
        top = int(
            browser.conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0]  # type: ignore[attr-defined]
        )
        middle = int(
            browser.conn.execute(  # type: ignore[attr-defined]
                "SELECT MAX(id) FROM nodes WHERE level = 1"
            ).fetchone()[0]
        )
        cluster_store.add_child(
            browser.conn,  # type: ignore[arg-type]
            top,
            middle,
            attached=False,
            similarity=None,
        )
    browser.sign_in()

    page = browser.node(_node_id(browser)).text  # type: ignore[attr-defined]
    start = page.index('class="crumbs"')
    crumbs = page[start : page.index("</nav>", start)]

    links = re.findall(r"/nodes/(\d+)\?", crumbs)
    assert links == [str(top), str(middle)]


def test_the_facts_come_before_the_hashes(browser: Browser) -> None:
    browser.sign_in()

    page = browser.node(_node_id(browser)).text  # type: ignore[attr-defined]
    hashes = page.index('<details class="hashes">')

    for fact in ("scribe-9", "1,234 in, 56 out"):
        assert page.index(fact) < hashes
    for digest in ("pr00mpth4sh", "sig-written"):
        assert page.index(digest) > hashes


def test_sections_of_one_file_are_told_apart_by_heading_and_lines(
    browser: Browser,
) -> None:
    raw = _guide_text()
    ids = _ingest_file(browser, "docs/guide.md", raw)
    assert len(ids) > 1
    topic = _topic_over(browser, ids)
    browser.sign_in()

    page = browser.node(topic).text  # type: ignore[attr-defined]

    rows = re.findall(
        r'<span class="heading">([^<]*)</span>'
        r'<span class="faint num nowrap">lines (\d+)(?:-(\d+))?</span>',
        page,
    )
    assert len(rows) == len(ids)
    assert len({heading for heading, *_ in rows}) == len(rows)
    lines = raw.decode().splitlines()
    for heading, first, last in rows:
        # the range really is where that text is in the file
        assert lines[int(first) - 1].lstrip("# ").startswith(heading[:5])
        assert int(last or first) <= len(lines)
    ends = sorted((int(f), int(last or f)) for _, f, last in rows)
    assert ends[0][0] == 1
    assert ends[-1][1] == len(lines)
    for (_, before), (after, _) in zip(ends, ends[1:], strict=False):
        assert after == before + 1


def test_the_section_list_filters_by_path(browser: Browser) -> None:
    browser.sign_in()
    node = _node_id(browser)

    page = browser.client.get(  # type: ignore[attr-defined]
        f"/ui/trees/{TREE}/nodes/{node}", params={"q": "WORSE"}
    ).text

    assert "worse.md" in page
    assert "edge.md" not in page
    assert "1 of 4" in page
    # a plain search box: Enter submits it without script, the script filters
    # as you type by swapping in this same list, so the list has its own id
    form = page[page.index('<form class="section-filter"') :]
    form = form[: form.index("</form>")]
    assert "<button" not in form
    assert 'class="visually-hidden" for="section-q"' in form
    assert 'id="section-list"' in page


def test_a_long_section_list_is_paged_and_a_link_finds_its_page(
    browser: Browser,
) -> None:
    ids = []
    with browser.conn:  # type: ignore[union-attr]
        for n in range(60):
            ids.append(_section(browser.conn, f"docs/many/f{n:02}.md", b"x\n"))
    topic = _topic_over(browser, ids)
    browser.sign_in()

    first = browser.node(topic).text  # type: ignore[attr-defined]
    last = browser.client.get(  # type: ignore[attr-defined]
        f"/ui/trees/{TREE}/nodes/{topic}", params={"section": ids[-1]}
    ).text

    assert len(re.findall(r'id="section-\d+"', first)) == 25
    assert "page 1 of 3" in first
    assert f'id="section-{ids[-1]}"' not in first
    assert f'id="section-{ids[-1]}"' in last
    assert "page 3 of 3" in last


def test_a_section_condensed_by_two_models_is_one_row(
    browser: Browser,
) -> None:
    node = _node_id(browser)
    with browser.conn:  # type: ignore[union-attr]
        digests = [
            r[0]
            for r in browser.conn.execute(  # type: ignore[attr-defined]
                "SELECT s.content_hash FROM node_members m "
                "JOIN sections s ON s.id = m.section_id WHERE m.node_id = ?",
                (node,),
            )
        ]
        for digest in digests:
            # the other model sorts BEFORE the recorded one and is written last,
            # so only the model filter, not row order, can pick it
            for model in ("scribe-9", "alpha-old"):
                condensations.upsert(
                    browser.conn,  # type: ignore[arg-type]
                    digest,
                    model,
                    f"by {model}",
                    1,
                    1,
                )
        browser.conn.execute(  # type: ignore[attr-defined]
            "UPDATE briefs SET source_model = 'scribe-9' WHERE node_id = ?",
            (node,),
        )
    browser.sign_in()

    page = browser.node(node).text  # type: ignore[attr-defined]
    ids = re.findall(r'id="section-(\d+)"', page)

    assert len(ids) == 4
    assert len(set(ids)) == 4
    assert "by scribe-9" in page
    assert "by alpha-old" not in page


def test_a_section_with_no_final_newline_counts_its_last_line(
    browser: Browser,
) -> None:
    sid = _section(browser.conn, "docs/tail.md", b"one\ntwo\nthree")
    node = _topic_over(browser, [sid])
    browser.sign_in()

    page = browser.node(node).text  # type: ignore[attr-defined]

    assert "lines 1-3<" in page


def test_the_edit_actions_sit_below_the_reading_for_an_admin(
    browser: Browser,
) -> None:
    _topic_over(browser, [_section(browser.conn, "docs/other.md", b"o\n")])
    browser.sign_in()

    page = browser.node(_node_id(browser)).text  # type: ignore[attr-defined]
    manage = page[page.index('id="manage"') :]
    brief = page[
        page.index('class="card brief-card"') : page.index('id="manage"')
    ]

    assert "/brief" in brief  # the brief is edited where it is read
    for action in ("rename", "note", "reparent", "merge", "split", "dissolve"):
        assert f"/{action}" in manage
    # each destructive one says what it will change before it runs
    assert "Folds this topic" in manage
    assert "re-filed under the nearest remaining topic" in manage
    assert "Replaced by narrower topics" in manage
    # moving a section is an edit too: tucked behind its own disclosure in
    # the open section, not shown beside what the section says
    move = page.index('class="move"')
    assert page.rfind('<summary class="twisty">Move</summary>', 0, move) > 0


def _ingest_from(
    browser: Browser, source_type: str, instance: str, path: str
) -> int:
    with browser.conn:  # type: ignore[union-attr]
        stored = store_unit(
            browser.conn,  # type: ignore[arg-type]
            Unit(path=path, body=_guide_text(), version="c0ffee"),
            "docs",
            source_type,
            instance,
            "c0ffee",
        )
    return _topic_over(browser, [sid for sid, _, _ in stored])


def test_a_git_section_links_to_its_file_at_the_synced_commit(
    browser: Browser,
) -> None:
    topic = _ingest_from(browser, "git", "github.com/acme/repo", "docs/g.md")
    browser.sign_in()

    page = browser.node(topic).text  # type: ignore[attr-defined]

    links = re.findall(r'<a href="(https://github[^"]+)"', page)
    assert links
    base = "https://github.com/acme/repo/blob/c0ffee/docs/g.md#L"
    assert all(link.startswith(base) for link in links)
    assert any("-L" in link for link in links)


@pytest.mark.parametrize(
    ("kind", "host"),
    [
        ("git", "git.internal/acme/repo"),
        ("confluence", "github.com/acme/repo"),
    ],
    ids=["unknown-host", "page"],
)
def test_a_section_with_no_file_to_open_shows_its_path_and_no_link(
    browser: Browser, kind: str, host: str
) -> None:
    topic = _ingest_from(browser, kind, host, "g.md")
    browser.sign_in()

    page = browser.node(topic).text  # type: ignore[attr-defined]

    assert "Open the file" not in page
    assert "g.md" in page
