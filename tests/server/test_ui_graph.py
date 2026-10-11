"""The node graph, drawn server-side.

Every state of the graph is a URL, so every assertion here is on the HTML that
URL returns — which is the whole reason the expand state is a query parameter
rather than something a script holds.
"""

from __future__ import annotations

import html
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
from hrono.server import graph
from hrono.server.app import create_app
from hrono.summarize import briefs

KEY = Fernet.generate_key()
TREE = "default"


class Browser:
    def __init__(
        self, client: TestClient, token: str, ids: dict, conn: object
    ) -> None:
        self.client = client
        self.token = token
        self.ids = ids
        self.conn = conn

    def sign_in(self) -> None:
        self.client.post("/ui/login", data={"token": self.token})

    def map_at(self, query: str) -> str:
        """The map at a RAW query string, so a test can send no open at all."""
        return self.client.get(f"/ui/trees/{TREE}/graph{query}").text

    def map(self, open: str = "") -> str:
        return self.client.get(f"/ui/trees/{TREE}/graph?open={open}").text


def _section(conn: object, path: str) -> int:
    body = f"{path} body\n".encode()
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
    """A root over two topics: one big and fresh, one small and stale."""
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    ids: dict[str, int] = {}
    with conn:
        big = cluster_store.add_leaf_node(
            conn,
            TREE,
            [
                (_section(conn, f"src/hrono/db/b{i}.py"), False, None)
                for i in range(6)
            ],
        )
        small = cluster_store.add_leaf_node(
            conn, TREE, [(_section(conn, "tests/cluster/s0.py"), False, None)]
        )
        briefs.upsert(
            conn,
            big,
            "Signing modules. The code that signs and verifies tokens.",
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature="sig",
            input_tokens=1,
            output_tokens=1,
        )
        # `small` gets NO brief: missing counts as stale, because an operator
        # looking for what needs work wants both in the same colour
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 1, 0, 't')",
            (TREE,),
        )
        root = int(conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0])
        for child in (big, small):
            cluster_store.add_child(
                conn, root, child, attached=False, similarity=None
            )
        ids.update(big=big, small=small, root=root)
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        # Tests write through `conn` after this point, and the worker polls
        # that same connection from its own thread.
        app.state.worker.stop()
        app.state.worker.join(timeout=5)
        yield Browser(client, token, ids, conn)
    conn.close()


def test_a_closed_root_draws_only_itself(browser: Browser) -> None:
    browser.sign_in()

    page = browser.map()

    # the map's own discs, not every circle on the page: the legend draws
    # example circles of its own
    assert page.count('class="disc"') == 1
    assert f"/nodes/{browser.ids['big']}" not in page


def test_a_closed_topic_with_children_is_marked(browser: Browser) -> None:
    # or an operator cannot tell a leaf from a branch they have not opened
    browser.sign_in()

    page = browser.map()

    # a right-pointing disclosure triangle, and the link it carries
    assert 'class="twist closed"' in page
    assert "Open — show the" in page


def test_opening_the_root_draws_its_children(browser: Browser) -> None:
    browser.sign_in()

    page = browser.map(open=str(browser.ids["root"]))

    assert page.count('class="disc"') == 3
    assert f"focus={browser.ids['big']}" in page
    assert f"focus={browser.ids['small']}" in page
    assert page.count('class="edge"') == 2  # root to each child


def test_a_leaf_is_not_marked_as_closed(browser: Browser) -> None:
    browser.sign_in()

    page = browser.map(open=str(browser.ids["root"]))

    # the root is open and the leaves have no children, so nothing on the page
    # claims to hide anything
    assert page.count('class="twist closed"') == 0


def test_size_follows_what_a_topic_holds(browser: Browser) -> None:
    browser.sign_in()
    with browser.client.app.state.db.connect() as conn:  # type: ignore[attr-defined]
        drawn = graph.build(conn, TREE, [browser.ids["root"]])

    by_id = {node.id: node for node in drawn.nodes}

    assert by_id[browser.ids["big"]].holds == 6
    assert by_id[browser.ids["small"]].holds == 1
    assert by_id[browser.ids["big"]].radius > by_id[browser.ids["small"]].radius


def test_a_missing_or_stale_brief_is_distinguishable(
    browser: Browser,
) -> None:
    browser.sign_in()
    with browser.client.app.state.db.connect() as conn:  # type: ignore[attr-defined]
        drawn = graph.build(conn, TREE, [browser.ids["root"]])

    by_id = {node.id: node for node in drawn.nodes}

    assert by_id[browser.ids["big"]].stale is False
    assert by_id[browser.ids["small"]].stale is True  # no brief at all


def test_toggling_is_a_link_so_a_view_can_be_shared(
    browser: Browser,
) -> None:
    browser.sign_in()
    root = browser.ids["root"]

    closed = browser.map()
    opened = browser.map(open=str(root))

    # closed: the root's own link ADDS it to `open`
    assert (
        f'href="/ui/trees/{TREE}/graph?tree={TREE}&amp;open={root}"' in closed
    )
    # opened: the same link now REMOVES it, so the toggle really toggles
    assert f'href="/ui/trees/{TREE}/graph?tree={TREE}&amp;open="' in opened
    # and a LEAF carries no toggle at all — there is nothing under it to
    # open — only the link that reads it
    assert (
        f'href="/ui/trees/{TREE}/graph?tree={TREE}&amp;'
        f"open={min(root, browser.ids['big'])},"
        f'{max(root, browser.ids["big"])}"' not in opened
    )
    assert (
        f'href="/ui/trees/{TREE}/graph?tree={TREE}&amp;open={root}'
        f'&amp;focus={browser.ids["big"]}"' in opened
    )


def test_an_empty_tree_says_so_rather_than_drawing_nothing(
    browser: Browser,
) -> None:
    browser.sign_in()

    page = browser.client.get("/ui/trees/empty/graph").text

    assert "has no topics yet" in page
    # no empty canvas is drawn — and the map that HAS one proves the marker
    # this looks for is the one the map really carries
    assert '<div class="canvas"' not in page
    assert '<div class="canvas"' in browser.map()


def test_a_hand_edited_open_parameter_cannot_break_the_page(
    browser: Browser,
) -> None:
    # a view cannot be invalid: a truncated or edited URL draws a smaller
    # graph, never a 500
    browser.sign_in()

    answer = browser.client.get(f"/ui/trees/{TREE}/graph?open=3,,notanid,")

    assert answer.status_code == 200


def test_more_than_one_root_is_drawn(browser: Browser) -> None:
    """A tree mid-repair can have several, and that is what to look at.

    Drawing only the first would hide exactly the orphan state triage
    reports — a subtree hanging off nothing.
    """
    with browser.client.app.state.db.write() as conn:  # type: ignore[attr-defined]
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 1, 1, 't')",
            (TREE,),
        )
    browser.sign_in()

    assert browser.map().count('class="disc"') == 2


def test_a_topic_is_labelled_by_where_its_sections_live(
    browser: Browser,
) -> None:
    """A weak model gives every topic the same brief, so the brief
    cannot be the label. The files underneath do not lie."""
    from hrono.server.graph import build

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    by_id = {node.id: node for node in drawn.nodes}
    assert by_id[browser.ids["big"]].where == "src/hrono/db"
    assert by_id[browser.ids["small"]].where == "tests/cluster"
    # an upper topic has no sections of its own, so it takes its descendants':
    # six of the seven below this root are the database
    assert by_id[browser.ids["root"]].where == "src/hrono/db"


def test_one_directory_holding_most_of_a_topic_names_it(
    browser: Browser,
) -> None:
    """The STRICT common prefix collapses to `src` for a topic that is
    obviously the database, so the label is the dominant directory."""
    from hrono.server.graph import build

    with browser.conn:  # type: ignore[union-attr]
        browser.conn.execute(  # type: ignore[attr-defined]
            "UPDATE sections SET path = ? WHERE path = ?",
            ("src/hrono/embed/stray.py", "src/hrono/db/b0.py"),
        )

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    by_id = {node.id: node for node in drawn.nodes}
    # five of six are still under src/hrono/db, which is over the share
    assert by_id[browser.ids["big"]].where == "src/hrono/db"


def test_a_straddling_topic_names_the_two_directories_and_their_shares(
    browser: Browser,
) -> None:
    """Naming the two ROOTS gives `src + tests` — the least telling segment
    of either path, and on the two biggest topics on the map. Each side is
    descended as far as IT is dominated instead."""
    from hrono.server.graph import build

    with browser.conn:  # type: ignore[union-attr]
        for index in range(3):
            browser.conn.execute(  # type: ignore[attr-defined]
                "UPDATE sections SET path = ? WHERE path = ?",
                (f"tests/cluster/b{index}.py", f"src/hrono/db/b{index}.py"),
            )

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    big = next(node for node in drawn.nodes if node.id == browser.ids["big"])
    # three and three: no directory holds it, so the label says both — at the
    # depth each of them IS held, not at their roots
    assert big.where == "src/hrono/db + tests/cluster"
    # and the proportions that make it a straddle are disclosed rather than
    # implied, because a 50/50 topic and a 59/41 one read the same otherwise
    assert big.spread == "src/hrono/db 50%, tests/cluster 50%"


def test_two_directories_of_the_SAME_NAME_are_said_once(
    browser: Browser,
) -> None:
    """`src/hrono/db + tests/db` is thirty-one characters in an eighteen
    character slot, and halved it becomes two stubs naming nothing. When both
    sides end in the same directory, that directory is the subject and the
    roots are what differ."""
    from hrono.server.graph import build

    with browser.conn:  # type: ignore[union-attr]
        for index in range(3):
            browser.conn.execute(  # type: ignore[attr-defined]
                "UPDATE sections SET path = ? WHERE path = ?",
                (f"tests/db/b{index}.py", f"src/hrono/db/b{index}.py"),
            )

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    big = next(node for node in drawn.nodes if node.id == browser.ids["big"])
    assert big.where == "db: src+tests"
    assert big.place == big.where  # short enough to reach the slot whole


def test_the_one_root_of_a_tree_is_named_by_what_it_was_built_FROM(
    browser: Browser,
) -> None:
    """The root straddles by construction, so `src + tests` would be the
    first label anyone reads, saying nothing; "whole tree" is true and just as
    empty. What it IS, is its sources."""
    from hrono.server.graph import build

    with browser.conn:  # type: ignore[union-attr]
        for index in range(3):
            browser.conn.execute(  # type: ignore[attr-defined]
                "UPDATE sections SET path = ? WHERE path = ?",
                (f"tests/db/b{index}.py", f"src/hrono/db/b{index}.py"),
            )
        browser.conn.execute(  # type: ignore[attr-defined]
            "UPDATE sections SET source = 'click'"
        )

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    root = next(node for node in drawn.nodes if node.id == browser.ids["root"])
    assert root.where == "click"
    # and what it spans is still said, in the tooltip and the panel
    assert "%" in root.spread and "src/hrono/db" in root.spread


def test_a_root_over_several_sources_is_counted_rather_than_listed(
    browser: Browser,
) -> None:
    """Three repository names end to end is a paragraph in an 18-character
    slot, and cut to fit it names none of them."""
    from hrono.server.graph import build

    with browser.conn:  # type: ignore[union-attr]
        for index in range(3):
            browser.conn.execute(  # type: ignore[attr-defined]
                "UPDATE sections SET path = ? WHERE path = ?",
                (f"tests/db/b{index}.py", f"src/hrono/db/b{index}.py"),
            )
        browser.conn.execute(  # type: ignore[attr-defined]
            "UPDATE sections SET source = 'repo-' || (id % 3)"
        )

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    root = next(node for node in drawn.nodes if node.id == browser.ids["root"])
    assert root.where == "3 sources"


def test_a_topic_one_directory_holds_discloses_no_spread(
    browser: Browser,
) -> None:
    """A share is only worth printing where the label had to name two places;
    on `src/hrono/db` it would be `100%`, which is noise."""
    from hrono.server.graph import build

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    big = next(node for node in drawn.nodes if node.id == browser.ids["big"])
    assert big.where == "src/hrono/db"
    assert big.spread == ""


def test_a_straddle_too_wide_for_the_slot_keeps_BOTH_sides(
    browser: Browser,
) -> None:
    """Cutting it as one string drops the whole of the second side."""
    from hrono.server.graph import LABEL_CHARS, build

    with browser.conn:  # type: ignore[union-attr]
        for index in range(3):
            browser.conn.execute(  # type: ignore[attr-defined]
                "UPDATE sections SET path = ? WHERE path = ?",
                (f"tests/cluster/b{index}.py", f"src/hrono/db/b{index}.py"),
            )

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    big = next(node for node in drawn.nodes if node.id == browser.ids["big"])
    assert len(big.where) > LABEL_CHARS  # the pair does not fit
    assert len(big.place) <= LABEL_CHARS
    # both sides survive the cut, each reduced to the directory it names
    assert big.place.startswith("db + clust")


def test_a_long_label_is_cut_from_the_front_to_fit_its_slot(
    browser: Browser,
) -> None:
    """A label wider than its slot collides with its neighbour's,
    and cutting a PATH at the tail leaves the half every topic shares."""
    from hrono.server.graph import LABEL_CHARS, build

    deep = "src/hrono/server/templates/partials"
    with browser.conn:  # type: ignore[union-attr]
        browser.conn.execute(  # type: ignore[attr-defined]
            "UPDATE sections SET path = ? WHERE path = ?",
            (f"{deep}/s0.py", "tests/cluster/s0.py"),
        )

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    small = next(
        node for node in drawn.nodes if node.id == browser.ids["small"]
    )
    assert small.where == deep  # the whole path is still there to hover
    assert len(small.place) <= LABEL_CHARS
    assert small.place.startswith("…/")
    assert deep.endswith(small.place.removeprefix("…/"))


def test_a_short_label_is_left_alone(browser: Browser) -> None:
    from hrono.server.graph import build

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    small = next(
        node for node in drawn.nodes if node.id == browser.ids["small"]
    )
    assert small.place == "tests/cluster"


def test_the_tree_hangs_DOWNWARDS_from_its_root(browser: Browser) -> None:
    """Not a left-to-right dendrogram, which is the shape a file explorer
    has. A tree has its root at the top and its children below."""
    from hrono.server.graph import build

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    by_id = {node.id: node for node in drawn.nodes}
    root, big, small = (
        by_id[browser.ids[key]] for key in ("root", "big", "small")
    )
    assert big.y > root.y and small.y > root.y  # below, not beside
    assert big.x != small.x  # siblings spread sideways
    # and the parent sits over the middle of the block it owns
    assert root.x == (big.x + small.x) / 2


def test_no_label_is_cut_by_either_edge_of_the_canvas(
    browser: Browser,
) -> None:
    """Labels sit UNDER their circle and centred on it, so the canvas has to
    keep half a label either side or the outermost names are sliced."""
    from hrono.server.graph import BOTTOM, LABEL_WIDTH, build

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    # half a label either side: a name is centred on its circle, so this is
    # what the outermost topic in a row needs not to be sliced
    assert min(node.x for node in drawn.nodes) >= LABEL_WIDTH / 2
    assert drawn.width - max(node.x for node in drawn.nodes) >= LABEL_WIDTH / 2
    assert drawn.height >= max(node.y for node in drawn.nodes) + BOTTOM


def test_the_canvas_starts_where_the_drawing_starts(
    browser: Browser,
) -> None:
    """The map must not open on a blank band with the first node below it."""
    from hrono.server.graph import MAX_RADIUS, build

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    # measured against a CIRCLE, not against TOP: asserting the margin is
    # whatever the module says the margin is would pass at any value
    blank = min(node.y for node in drawn.nodes) - MAX_RADIUS
    assert blank <= MAX_RADIUS


def test_siblings_STAY_ON_ONE_LEVEL_however_many_there_are(
    browser: Browser,
) -> None:
    """A wide family must not WRAP onto further rows to fit the map in one
    window. That puts a topic's right-hand subtree UNDER its left-hand
    one, and two subtrees stacked read as one beneath the other rather than
    as siblings. The canvas gets as wide as the tree instead."""
    from hrono.server.graph import SLOT, build

    with browser.conn:  # type: ignore[union-attr]
        for index in range(14):
            leaf = cluster_store.add_leaf_node(
                browser.conn,  # type: ignore[arg-type]
                TREE,
                [
                    (
                        _section(browser.conn, f"src/w{index}/x.py"),
                        False,
                        None,
                    )
                ],
            )
            cluster_store.add_child(
                browser.conn,  # type: ignore[arg-type]
                browser.ids["root"],
                leaf,
                attached=False,
                similarity=None,
            )

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    assert len(drawn.nodes) == 17  # the root and sixteen leaves
    kids = [node for node in drawn.nodes if node.id != browser.ids["root"]]
    assert len({node.y for node in kids}) == 1  # all on the same level
    assert len({node.x for node in kids}) == len(kids)  # each its own column
    # and the canvas grew to hold them rather than folding them under one
    # another: sixteen slots is wider than any window this is drawn in
    assert drawn.width >= SLOT * len(kids)


def test_the_canvas_is_only_as_deep_as_what_is_DRAWN(
    browser: Browser,
) -> None:
    """A collapsed map that reserved a row per level of the whole tree would
    be mostly blank paper."""
    from hrono.server.graph import build

    closed = build(browser.conn, TREE, [])  # type: ignore[arg-type]
    opened = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    assert closed.height < opened.height


def _root(browser: Browser) -> int:
    return int(
        browser.conn.execute(  # type: ignore[attr-defined]
            "SELECT MAX(id) FROM nodes"
        ).fetchone()[0]
    )


def _child_of(browser: Browser, parent: int) -> int:
    """A leaf under `parent`, made the way the fixture makes them."""
    node = cluster_store.add_leaf_node(
        browser.conn,  # type: ignore[arg-type]
        TREE,
        [(_section(browser.conn, f"pkg/mod/f{_child_of.n}.md"), False, None)],
    )
    _child_of.n += 1  # type: ignore[attr-defined]
    cluster_store.add_child(
        browser.conn,  # type: ignore[arg-type]
        parent,
        node,
        attached=False,
        similarity=None,
    )
    return node


_child_of.n = 0  # type: ignore[attr-defined]


def test_every_child_is_joined_to_its_parent_by_ONE_connector(
    browser: Browser,
) -> None:
    """A connector per child, never a line to nowhere — the wide layout has
    to keep that as the row it draws grows."""
    root = _root(browser)
    with browser.conn:  # type: ignore[union-attr]
        for _ in range(9):
            _child_of(browser, root)

    drawn = graph.build(browser.conn, TREE, [root])  # type: ignore[arg-type]

    assert len(drawn.edges) == len(drawn.nodes) - 1
    assert all(line.startswith("M") for line in drawn.edges)


def test_the_board_opens_on_the_ROOT_not_on_its_left_edge(
    browser: Browser,
) -> None:
    """A canvas as wide as the tree has no meaningful left edge, and
    landing there puts the reader in a corner of a map whose subject is in
    the middle."""
    root = _root(browser)
    with browser.conn:  # type: ignore[union-attr]
        for _ in range(9):
            _child_of(browser, root)

    drawn = graph.build(browser.conn, TREE, [root])  # type: ignore[arg-type]

    placed = next(node for node in drawn.nodes if node.id == root)
    assert drawn.home == placed.x
    # and that is not where a scroll box starts on its own
    assert drawn.home > drawn.width / 4


def test_where_the_board_opens_REACHES_the_page(browser: Browser) -> None:
    """A number the page does not carry cannot move anything."""
    root = _root(browser)
    with browser.conn:  # type: ignore[union-attr]
        for _ in range(9):
            _child_of(browser, root)
    browser.sign_in()

    page = browser.map(str(root))
    drawn = graph.build(browser.conn, TREE, [root])  # type: ignore[arg-type]

    assert f'data-home="{drawn.home}"' in page


def test_reading_a_topic_opens_a_PANEL_and_leaves_the_map_drawn(
    browser: Browser,
) -> None:
    """Clicking a topic must not navigate away from the tree, which would
    throw away the thing the click was asking about."""
    browser.sign_in()
    big, root = browser.ids["big"], browser.ids["root"]

    page = browser.client.get(
        f"/ui/trees/{TREE}/graph?open={root}&focus={big}"
    ).text

    assert '<aside class="panel"' in page
    assert "Signing modules." in page  # its brief, read beside the map
    assert "src/hrono/db/b0.py" in page  # and what it is made of
    assert page.count('class="disc"') == 3  # the map is still all there


def test_the_panel_keeps_the_way_to_the_controls_that_CHANGE_a_topic(
    browser: Browser,
) -> None:
    """The edits are admin-gated on the topic page; copying the forms here
    would be a second, weaker place for the same permission rule."""
    browser.sign_in()
    big = browser.ids["big"]

    page = browser.client.get(f"/ui/trees/{TREE}/graph?focus={big}").text

    assert f'href="/ui/trees/{TREE}/nodes/{big}?tree={TREE}"' in page
    assert "/rename" not in page  # no edit form was duplicated into the map
    assert "/dissolve" not in page


def test_the_panel_closes_back_to_the_map_it_was_opened_from(
    browser: Browser,
) -> None:
    """Closing must not also throw away the expand state and the overlays
    the reader had set up to ask the question."""
    browser.sign_in()
    big, root = browser.ids["big"], browser.ids["root"]

    page = browser.client.get(
        f"/ui/trees/{TREE}/graph?open={root}&edges=pull&focus={big}"
    ).text

    # anchored to the CLOSE control. The focused topic's own disc links to
    # the same place — clicking it again closes the panel too — so a bare
    # search for the URL passes with no close button on the page at all
    assert (
        f'href="/ui/trees/{TREE}/graph?tree={TREE}'
        f'&amp;open={root}&amp;edges=pull" aria-label="Close the panel"'
    ) in page


def test_a_focus_on_a_topic_that_is_not_there_draws_no_panel(
    browser: Browser,
) -> None:
    """A focus is a VIEW of the map, and a view cannot be invalid: a stale
    link draws the map, never an error page over it."""
    browser.sign_in()

    answer = browser.client.get(f"/ui/trees/{TREE}/graph?focus=99999")

    assert answer.status_code == 200
    # the MARKUP, not the word: the stylesheet names `.panel` on every page
    assert '<aside class="panel"' not in answer.text
    assert (
        '<aside class="panel"'
        in browser.client.get(
            f"/ui/trees/{TREE}/graph?focus={browser.ids['big']}"
        ).text
    )


def test_an_upper_topic_in_the_panel_lists_the_topics_under_it(
    browser: Browser,
) -> None:
    """A topic that holds topics has no sections to show, and listing none
    would say it was empty."""
    browser.sign_in()
    root = browser.ids["root"]

    page = browser.client.get(f"/ui/trees/{TREE}/graph?focus={root}").text

    assert "2 topics" in page
    assert f"focus={browser.ids['big']}" in page
    assert f"focus={browser.ids['small']}" in page


def test_collapse_still_means_collapsed(browser: Browser) -> None:
    """`open=` present and EMPTY is what the Collapse link sends.

    Treating that the same as absent would make Collapse a no-op — the trap
    in giving an absent parameter a non-empty default.
    """
    browser.sign_in()

    both = (browser.map_at(""), browser.map_at("?open="))

    assert both[0].count('class="disc"') > both[1].count('class="disc"')


def test_collapse_actually_collapses(browser: Browser) -> None:
    """Collapse must not expand.

    An absent `open` means "a first visit, open some levels", so a Collapse
    link that drops empty parameters becomes Expand. The link has to say
    `open=` out loud.
    """
    browser.sign_in()

    page = browser.map_at("")
    collapse = re.search(r'href="([^"]*)"[^>]*>Collapse<', page)

    assert collapse is not None
    assert "open=" in collapse.group(1)
    after = browser.client.get(_href(collapse)).text
    assert after.count('class="disc"') < page.count('class="disc"')


def test_expand_all_opens_every_topic_that_has_one(
    browser: Browser,
) -> None:
    browser.sign_in()

    page = browser.map_at("?open=")
    expand = re.search(r'href="([^"]*)"[^>]*>Expand all<', page)

    assert expand is not None
    after = browser.client.get(_href(expand)).text
    assert after.count('class="disc"') > page.count('class="disc"')


def test_a_first_visit_shows_the_shape_not_the_whole_tree(
    browser: Browser,
) -> None:
    """Two levels: the root and what is directly under it."""
    from hrono.server.ui.views import OPEN_DEPTH

    assert OPEN_DEPTH == 2
    # the shared fixture is two levels deep, where "two open" and "all open"
    # are the same picture — a third level is what makes the rule observable
    with browser.conn:  # type: ignore[union-attr]
        browser.conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 2, 0, 't')",
            (TREE,),
        )
        crown = int(
            browser.conn.execute(  # type: ignore[attr-defined]
                "SELECT MAX(id) FROM nodes"
            ).fetchone()[0]
        )
        cluster_store.add_child(
            browser.conn,  # type: ignore[arg-type]
            crown,
            _root(browser),
            attached=False,
            similarity=None,
        )
    browser.sign_in()

    first = browser.map_at("")
    everything = browser.client.get(
        _href(re.search(r'href="([^"]*)"[^>]*>Expand all<', first))
    ).text

    assert first.count('class="disc"') < everything.count('class="disc"')


def _href(found: object) -> str:
    """The URL a browser would follow, not the escaped one in the markup.

    Jinja escapes `&` in an attribute, so requesting the raw capture asks for
    a parameter called `amp;open` and the real one goes missing — which looks
    exactly like the bug under test.
    """
    assert found is not None
    return html.unescape(found.group(1))  # type: ignore[attr-defined]


def test_each_top_level_subtree_gets_its_own_tint(browser: Browser) -> None:
    """A glance should say which branch a topic is in.

    Taken from the root's CHILDREN, not from the roots: with one root every
    topic would share a tint and the whole thing would be pointless.
    """
    from hrono.server.graph import build

    drawn = build(browser.conn, TREE, [_root(browser)])  # type: ignore[arg-type]
    by_id = {node.id: node.branch for node in drawn.nodes}

    assert by_id[_root(browser)] == 0  # the trunk belongs to all of them
    kids = [b for node, b in by_id.items() if node != _root(browser)]
    assert len(set(kids)) == len(kids)  # two siblings, two tints
    assert 0 not in kids


def test_a_brief_that_needs_rewriting_outranks_its_branch_tint(
    browser: Browser,
) -> None:
    """The one state on the map that must never be out-shouted.

    A themed tint selector would out-specify the stale rule and a topic needing
    a brief would keep its branch colour in dark mode, so the tint is a custom
    property and `stale` is last at the same specificity.
    """
    browser.sign_in()

    page = browser.map_at("")

    sheet = page[page.index("<style>") : page.index("</style>")]
    assert "svg .stale { --tint: var(--warn); }" in sheet
    assert sheet.index("svg .b1 { --tint") < sheet.index("svg .stale { --tint")
    # and no rule sets fill per branch, which is what would break it
    assert "svg .b1 circle.disc { fill:" not in sheet


def test_a_tint_is_reused_rather_than_a_branch_going_unmarked(
    browser: Browser,
) -> None:
    """More subtrees than tints is a repeated colour, never a bare one.

    A repeated tint is a smaller lie than an unmarked branch: the colour says
    "these are siblings", it never says "this is branch four".
    """
    from hrono.server.graph import TINTS, build

    root = _root(browser)
    with browser.conn:  # type: ignore[union-attr]
        for _ in range(TINTS + 2):
            _child_of(browser, root)

    drawn = build(browser.conn, TREE, [root])  # type: ignore[arg-type]

    tints = {node.branch for node in drawn.nodes if node.id != root}
    assert tints and tints <= set(range(1, TINTS + 1))


def test_a_first_visit_puts_no_sentinel_in_its_own_links(
    browser: Browser,
) -> None:
    """`NO_OPEN` means "the URL carried no `open`". Handing it back to the URL
    builder put a literal `open=%00` into every link on a first visit —
    harmless, because it round-trips to the same sentinel, and unpastable."""
    browser.sign_in()

    page = browser.map_at("")

    assert "%00" not in page and "\x00" not in page


def test_a_child_in_the_panel_links_to_the_map_the_reader_IS_ON(
    browser: Browser,
) -> None:
    """The panel's child links must not be a bare `?focus=`: reading down one
    level would throw away the expand state and every overlay the reader had
    set up, collapsing the map under them."""
    browser.sign_in()
    root = browser.ids["root"]

    page = browser.client.get(
        f"/ui/trees/{TREE}/graph?open={root}&edges=proximity&focus={root}"
    ).text

    child = browser.ids["big"]
    assert (
        f'href="/ui/trees/{TREE}/graph?tree={TREE}&amp;open={root}'
        f'&amp;edges=proximity&amp;focus={child}"' in page
    )


def test_an_overlay_stays_on_when_a_topic_is_opened(
    browser: Browser,
) -> None:
    """A reader turns `proximity` on to find a merge, then opens the topic it
    pointed at — and the chevron's own URL dropped `edges`, so the drawing
    they opened it to read came back blank."""
    browser.sign_in()
    root = browser.ids["root"]

    page = browser.client.get(
        f"/ui/trees/{TREE}/graph?open=&edges=proximity"
    ).text

    assert (
        f'href="/ui/trees/{TREE}/graph?tree={TREE}&amp;open={root}'
        f'&amp;edges=proximity"' in page
    )


def test_an_overlay_toggled_on_a_collapsed_map_leaves_it_collapsed(
    browser: Browser,
) -> None:
    """The same rule for the overlay toggle, which builds its own URL: it must
    keep an EMPTY `open`, because an absent `open` means a first visit."""
    browser.sign_in()

    page = browser.map(open="")

    assert (
        f'href="/ui/trees/{TREE}/graph?tree={TREE}&amp;open=&amp;edges=pull"'
        in page
    )


def test_a_reply_that_is_not_a_brief_draws_as_needing_one(
    browser: Browser,
) -> None:
    # the model talking back is a topic without a brief, on the map too
    database = browser.client.app.state.db  # type: ignore[attr-defined]
    browser.client.app.state.worker.stop()  # type: ignore[attr-defined]
    browser.client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
    with database.write() as conn:
        briefs.upsert(
            conn,
            browser.ids["big"],
            "Your prompt got blocked by a hook. Strip the secret and resend.",
            model_name="m",
            prompt_name="brief",
            prompt_hash="h",
            member_signature="sig",
            input_tokens=1,
            output_tokens=1,
        )
        drawn = graph.build(conn, TREE, [browser.ids["root"]])

    by_id = {node.id: node for node in drawn.nodes}

    assert by_id[browser.ids["big"]].stale is True


# ------------------------------------------------------------ the two views


def _view_of(page: str) -> str:
    found = re.search(r'id="board"[^>]*data-view="([a-z]+)"', page)
    assert found is not None, "no board on the page"
    return found.group(1)


def test_a_small_tree_opens_as_circles_and_a_big_one_as_the_list(
    browser: Browser, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Circles show a small tree whole; past a few dozen topics they are a
    row wider than any window, so the default flips to the list."""
    from hrono.server.ui import views

    browser.sign_in()
    assert _view_of(browser.map_at("")) == "circles"

    monkeypatch.setattr(views, "LIST_AT", 2)  # the fixture has three topics

    assert _view_of(browser.map_at("")) == "list"
    # and a view the reader chose beats the default either way
    assert _view_of(browser.map_at("?view=circles")) == "circles"


def test_the_list_is_one_row_per_shown_topic_indented_under_its_parent(
    browser: Browser,
) -> None:
    browser.sign_in()
    root, big, small = (browser.ids[k] for k in ("root", "big", "small"))

    page = browser.map_at(f"?view=list&open={root}")

    rows = re.findall(
        r'<tr[^>]*style="--depth: (\d+)">.*?focus=(\d+)', page, re.S
    )
    assert [(int(d), int(n)) for d, n in rows] == [
        (0, root),
        (1, big),
        (1, small),
    ]
    assert 'class="disc"' not in page  # no circles drawn under the list
    # the open root says so, to a screen reader as well as by its chevron
    drawn = graph.build(browser.conn, TREE, [root])  # type: ignore[arg-type]
    assert 'aria-expanded="true"' in page
    assert f'aria-label="Close {html.escape(drawn.nodes[0].name)}"' in page


def test_a_closed_topic_in_the_list_opens_to_its_children(
    browser: Browser,
) -> None:
    browser.sign_in()

    closed = browser.map_at("?view=list&open=")
    chevron = re.search(
        r'<a class="fold" href="([^"]*)"\s+aria-expanded="false"', closed
    )

    assert closed.count("<tr") == 2  # the header row and the root
    opened = browser.client.get(_href(chevron)).text
    assert opened.count("<tr") == 4
    assert _view_of(opened) == "list"


def test_every_map_link_in_the_list_keeps_the_list(browser: Browser) -> None:
    """A chevron, a name, the fold control, a child in the panel and the
    panel's close all go back to the map: each must land on the SAME view,
    or reading a topic flips the reader back to circles."""
    browser.sign_in()
    root, big = browser.ids["root"], browser.ids["big"]

    page = browser.map_at(f"?view=list&open={root}&focus={root}")

    # the map's own links: the header's way TO the map is not one of them
    mapped = page[page.index('id="controls"') :]
    graph_links = [
        html.unescape(href)
        for href in re.findall(r'href="(/ui/trees/[^"]*/graph\?[^"]*)"', mapped)
    ]
    switch = [link for link in graph_links if "view=circles" in link]
    rest = [link for link in graph_links if link not in switch]
    assert len(switch) == 1  # the one way over to the circles
    assert rest and all("view=list" in link for link in rest), rest
    assert any(f"focus={big}" in link for link in rest)  # a panel child


def test_a_view_nobody_chose_stays_out_of_the_links(browser: Browser) -> None:
    """Only the switch names a view when the reader has not picked one, so
    the URLs every other test pins stay what they were; a made-up view is
    the same as none."""
    browser.sign_in()

    for query in ("", "?view=bogus"):
        page = browser.map_at(query)
        named = re.findall(r'href="[^"]*/graph\?[^"]*view=(\w+)', page)
        assert sorted(named) == ["circles", "list"], query
        assert _view_of(page) == "circles"


def test_the_controls_do_not_repeat_the_tree_name(browser: Browser) -> None:
    """The tree picker at the top of the page already names it."""
    browser.sign_in()

    page = browser.map_at("")

    controls = page[page.index('id="controls"') :]
    controls = controls[: controls.index("</div>")]
    said = re.sub(r"<[^>]+>|\s+", " ", re.sub(r'"[^"]*"', "", controls))
    assert TREE not in said
    assert "3 shown" in said  # a quiet count instead
    assert 'class="map-title"' not in page


def test_every_legend_key_is_three_words_at_most(browser: Browser) -> None:
    """Detail goes in the key's tooltip, not its label."""
    browser.sign_in()

    page = browser.map_at("")

    legend = page[page.index('<ul class="keys">') :]
    legend = legend[: legend.index("</ul>")]
    keys = re.findall(r"<li[^>]*>(.*?)</li>", legend, re.S)
    words = [re.sub(r"<[^>]+>", " ", key).split() for key in keys]
    assert len(words) == 5
    assert all(0 < len(key) <= 3 for key in words), words
    assert all(re.search(r'<li title="[^"]{20,}"', legend) for _ in keys)


def test_the_panel_says_its_facts_as_text_and_its_action_as_a_button(
    browser: Browser,
) -> None:
    """A count in a bordered chip reads as a button and is not one; the one
    action, to the topic page, is drawn as the primary button."""
    browser.sign_in()
    big = browser.ids["big"]

    page = browser.client.get(f"/ui/trees/{TREE}/graph?focus={big}").text

    panel = page[page.index('<aside class="panel"') :]
    panel = panel[: panel.index("<h3>")]
    assert "chip" not in panel
    assert "<dt>Holds</dt>" in panel and "6 sections" in panel
    assert "%" not in panel  # no unexplained shares of folders
    assert re.search(
        rf'class="btn primary panel-out" href="/ui/trees/{TREE}/nodes/{big}',
        panel,
    )


def test_no_name_on_the_map_wears_a_halo(browser: Browser) -> None:
    """A stroke in the canvas colour drew a pale outline round every label."""
    browser.sign_in()

    page = browser.map_at("")

    sheet = page[page.index("<style>") : page.index("</style>")]
    rule = re.search(r"\nsvg text \{([^}]*)\}", sheet)
    assert rule is not None
    assert "stroke" not in rule.group(1)
    assert "paint-order" not in rule.group(1)
