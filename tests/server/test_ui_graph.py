"""#183 (T50.1/.2): the node graph, drawn server-side.

Every state of the graph is a URL, so every assertion here is on the HTML that
URL returns — which is the whole reason the expand state is a query parameter
rather than something a script holds.
"""

from __future__ import annotations

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
            "Signing modules.",
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
    assert f"/nodes/{browser.ids['big']}" in page
    assert f"/nodes/{browser.ids['small']}" in page
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
    # open — only the link to its own page
    assert (
        f'href="/ui/trees/{TREE}/graph?tree={TREE}&amp;'
        f"open={min(root, browser.ids['big'])},"
        f'{max(root, browser.ids["big"])}"' not in opened
    )
    assert f"/nodes/{browser.ids['big']}" in opened


def test_an_empty_tree_says_so_rather_than_drawing_nothing(
    browser: Browser,
) -> None:
    browser.sign_in()

    page = browser.client.get("/ui/trees/empty/graph").text

    assert "has no topics yet" in page
    assert '<div class="canvas">' not in page  # no empty canvas is drawn


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

    Drawing only the first would hide exactly the state #124 and #163 are
    about — a subtree hanging off nothing.
    """
    with browser.client.app.state.db.write() as conn:  # type: ignore[attr-defined]
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 1, 1, 't')",
            (TREE,),
        )
    browser.sign_in()

    assert browser.map().count('class="disc"') == 2


def test_a_topic_is_labelled_by_where_its_chunks_live(
    browser: Browser,
) -> None:
    """#198: a weak model gives every topic the same brief, so the brief
    cannot be the label. The files underneath do not lie."""
    from hrono.server.graph import build

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    by_id = {node.id: node for node in drawn.nodes}
    assert by_id[browser.ids["big"]].where == "src/hrono/db"
    assert by_id[browser.ids["small"]].where == "tests/cluster"
    # an upper topic has no chunks of its own, so it takes its descendants':
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


def test_a_topic_no_directory_holds_is_named_by_what_it_straddles(
    browser: Browser,
) -> None:
    from hrono.server.graph import build

    with browser.conn:  # type: ignore[union-attr]
        for index in range(3):
            browser.conn.execute(  # type: ignore[attr-defined]
                "UPDATE sections SET path = ? WHERE path = ?",
                (f"tests/db/b{index}.py", f"src/hrono/db/b{index}.py"),
            )

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    by_id = {node.id: node for node in drawn.nodes}
    # three and three: no directory holds it, so the label says both
    assert by_id[browser.ids["big"]].where in ("src + tests", "tests + src")


def test_a_long_label_is_cut_from_the_front_to_fit_its_slot(
    browser: Browser,
) -> None:
    """#197/#198: a label wider than its slot collides with its neighbour's,
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
    assert len(small.label) <= LABEL_CHARS
    assert small.label.startswith("…/")
    assert deep.endswith(small.label.removeprefix("…/"))


def test_a_short_label_is_left_alone(browser: Browser) -> None:
    from hrono.server.graph import build

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    small = next(
        node for node in drawn.nodes if node.id == browser.ids["small"]
    )
    assert small.label == "tests/cluster"


def test_the_tree_hangs_DOWNWARDS_from_its_root(browser: Browser) -> None:
    """#198: it was a left-to-right dendrogram, which is the shape a file
    explorer has. A tree has its root at the top and its children below."""
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
    """#198: the map opened on a blank band with the first node below it."""
    from hrono.server.graph import MAX_RADIUS, build

    drawn = build(browser.conn, TREE, [browser.ids["root"]])  # type: ignore[arg-type]

    # measured against a CIRCLE, not against TOP: asserting the margin is
    # whatever the module says the margin is would pass at any value
    blank = min(node.y for node in drawn.nodes) - MAX_RADIUS
    assert blank <= MAX_RADIUS


def test_children_WRAP_instead_of_running_off_the_page(
    browser: Browser,
) -> None:
    """#198: twenty-six siblings on one row was 4,000px of canvas and three
    screenfuls. They are packed into rows the page can hold instead."""
    from hrono.server.graph import GUTTER, PAD, ROW_WIDTH, SLOT, build

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
    rows: dict[float, int] = {}
    for node in drawn.nodes:
        rows[node.y] = rows.get(node.y, 0) + 1
    assert len(rows) >= 4  # the root, and its children over three rows
    assert max(rows.values()) <= ROW_WIDTH / SLOT  # wrapped BY WIDTH
    assert drawn.width <= ROW_WIDTH + 2 * PAD  # and the page still holds it
    # a block that wrapped keeps a lane down its left: the connector into the
    # second row runs there, and a line drawn between the rows instead would
    # be read through their names
    assert min(node.x for node in drawn.nodes) >= PAD + GUTTER + SLOT / 2


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


def test_a_connector_that_travels_past_other_topics_is_marked(
    browser: Browser,
) -> None:
    """#197: it looked like a box drawn around the topics it passed.

    A connector to a wrapped row steps out, drops and comes back. At the same
    weight as an ordinary connector those three runs read as a container
    around whatever sits inside them — a grouping the tree does not have.
    """
    from hrono.server.graph import ROW_WIDTH, SLOT, build

    root = _root(browser)
    with browser.conn:  # type: ignore[union-attr]
        for _ in range(int(ROW_WIDTH // SLOT) + 2):
            _child_of(browser, root)

    drawn = build(browser.conn, TREE, [root])  # type: ignore[arg-type]

    assert any(line.past for line in drawn.edges)  # the wrapped row
    assert any(not line.past for line in drawn.edges)  # the first row


def test_a_tree_that_does_not_wrap_marks_nothing(browser: Browser) -> None:
    # nothing to travel past, so nothing is drawn subordinate
    drawn = graph.build(browser.conn, TREE, [_root(browser)])  # type: ignore[arg-type]

    assert not any(line.past for line in drawn.edges)


def test_the_marked_connectors_are_the_ones_drawn_faint(
    browser: Browser,
) -> None:
    """The mark has to reach the page, or it decorates nothing."""
    from hrono.server.graph import ROW_WIDTH, SLOT

    root = _root(browser)
    with browser.conn:  # type: ignore[union-attr]
        for _ in range(int(ROW_WIDTH // SLOT) + 2):
            _child_of(browser, root)
    browser.sign_in()

    page = browser.map(str(root))

    assert 'class="edge past"' in page
    assert "svg .edge.past" in page  # and the rule that makes it subordinate
