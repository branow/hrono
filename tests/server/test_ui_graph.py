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
    def __init__(self, client: TestClient, token: str, ids: dict) -> None:
        self.client = client
        self.token = token
        self.ids = ids

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
            [(_section(conn, f"b{i}.md"), False, None) for i in range(6)],
        )
        small = cluster_store.add_leaf_node(
            conn, TREE, [(_section(conn, "s0.md"), False, None)]
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
        yield Browser(client, token, ids)
    conn.close()


def test_a_closed_root_draws_only_itself(browser: Browser) -> None:
    browser.sign_in()

    page = browser.map()

    assert page.count("<circle") == 1
    assert f"/nodes/{browser.ids['big']}" not in page


def test_a_closed_topic_with_children_is_marked(browser: Browser) -> None:
    # or an operator cannot tell a leaf from a branch they have not opened
    browser.sign_in()

    page = browser.map()

    assert 'class="closed"' in page
    assert 'class="more">+</text>' in page


def test_opening_the_root_draws_its_children(browser: Browser) -> None:
    browser.sign_in()

    page = browser.map(open=str(browser.ids["root"]))

    assert page.count("<circle") == 3
    assert f"/nodes/{browser.ids['big']}" in page
    assert f"/nodes/{browser.ids['small']}" in page
    assert page.count("<line") == 2  # root to each child


def test_a_leaf_is_not_marked_as_closed(browser: Browser) -> None:
    browser.sign_in()

    page = browser.map(open=str(browser.ids["root"]))

    # one closed marker at most — the root is open, the leaves have no children
    assert page.count('class="more">+</text>') == 0


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
    # and a child carries a link that opens the child, not the root
    assert (
        f'href="/ui/trees/{TREE}/graph?tree={TREE}&amp;'
        f"open={min(root, browser.ids['big'])},"
        f'{max(root, browser.ids["big"])}"' in opened
    )


def test_an_empty_tree_says_so_rather_than_drawing_nothing(
    browser: Browser,
) -> None:
    browser.sign_in()

    page = browser.client.get("/ui/trees/empty/graph").text

    assert "has no topics yet" in page
    assert "<svg" not in page


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

    assert browser.map().count("<circle") == 2
