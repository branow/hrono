"""#184 (T50.3): non-tree edges — pull, proximity, propagation.

Every edge here comes from REAL stored vectors through `combined_vector`: the
`assignment_similarity` column plays no part, which is the point — a pull edge
computed from what a chunk's placement CLAIMED would agree with the tree by
construction and could never contradict it.
"""

from __future__ import annotations

import json
import math
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.cluster.blend import path_body, register_path_bodies
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.db.update_log import record
from hrono.embed.store import upsert_vector
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.registry import store as registry_store
from hrono.server import overlays
from hrono.server.app import create_app

KEY = Fernet.generate_key()
TREE = "default"
MODEL = "emb"
PATH = "docs/a.md"


def _unit(vector: tuple[float, float]) -> tuple[float, float]:
    norm = math.sqrt(sum(v * v for v in vector))
    return (vector[0] / norm, vector[1] / norm)


def _model() -> str:
    return json.dumps(
        {
            "name": MODEL,
            "kind": "embedding",
            "connection": None,
            "model": "fake",
            "params": {"dims": 2},
        }
    )


def _section(conn: object, body: str, vector: tuple[float, float]) -> int:
    raw = body.encode()
    digest = content_hash(raw)
    istore.upsert_content(conn, digest, raw)  # type: ignore[arg-type]
    upsert_vector(conn, digest, MODEL, _unit(vector))  # type: ignore[arg-type]
    return istore.insert_section(
        conn,  # type: ignore[arg-type]
        source="docs",
        address=Address("git", "ex/docs", PATH, "v1"),
        start=0,
        end=len(raw),
        content_hash=digest,
        ordinal=0,
    )


class Browser:
    def __init__(self, client: TestClient, token: str, conn: object) -> None:
        self.client = client
        self.token = token
        self.conn = conn
        self.root = 0
        self.leaves: tuple[int, ...] = ()
        self.elsewhere = 0  # a leaf under a DIFFERENT parent

    def sign_in(self) -> None:
        self.client.post("/ui/login", data={"token": self.token})

    def map(self, edges: str = "") -> str:
        return self.client.get(
            f"/ui/trees/{TREE}/graph?open={self.root}&edges={edges}"
        ).text

    def links(
        self, *kinds: str, drawn: tuple[int, ...] | None = None
    ) -> tuple[overlays.Link, ...]:
        visible = drawn if drawn is not None else (self.root, *self.leaves)
        return overlays.build(self.conn, TREE, visible, kinds).links  # type: ignore[arg-type]


@pytest.fixture
def browser(tmp_path: Path) -> Iterator[Browser]:
    """Three leaves under a root, with vectors chosen to make each edge.

    A and B point opposite ways, so they are NOT proximate; C sits almost on
    top of B, so they are. A holds one chunk pointing B's way, which is the
    pull. The path vector is shared, so a combined dot is
    `0.5 + 0.5 * content_dot` and TAU (0.70) means a content dot of 0.4.

    D is the control. It sits under a DIFFERENT parent and is nearer to both
    B and to A's stray chunk than anything else — so a proximity rule that
    forgot to check the parent would join it to B, and a centroid set that
    ignored what is DRAWN would hand A's pull to a topic nobody can see.
    """
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    registry_store.insert(
        conn,
        "models",
        MODEL,
        _model(),
        None,
        "t",
    )
    with conn:
        from hrono.cluster.blend import path_body, register_path_bodies

        register_path_bodies(conn, [PATH])
        upsert_vector(conn, content_hash(path_body(PATH)), MODEL, (1.0, 0.0))

        a = cluster_store.add_leaf_node(
            conn,
            TREE,
            [
                (_section(conn, "a1", (1.0, 0.0)), False, None),
                (_section(conn, "a2", (1.0, 0.02)), False, None),
                # the chunk that belongs next door
                (_section(conn, "a3", (-1.0, 0.0)), False, None),
            ],
        )
        b = cluster_store.add_leaf_node(
            conn, TREE, [(_section(conn, "b1", (-1.0, 0.03)), False, None)]
        )
        c = cluster_store.add_leaf_node(
            conn, TREE, [(_section(conn, "c1", (-0.95, 0.31)), False, None)]
        )
        d = cluster_store.add_leaf_node(
            conn, TREE, [(_section(conn, "d1", (-1.0, 0.0)), False, None)]
        )

        def upper() -> int:
            conn.execute(
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES (?, 1, 0, 't')",
                (TREE,),
            )
            return int(conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0])

        root, other_root = upper(), upper()
        for leaf in (a, b, c):
            cluster_store.add_child(
                conn, root, leaf, attached=False, similarity=None
            )
        cluster_store.add_child(
            conn, other_root, d, attached=False, similarity=None
        )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        # The worker polls the SAME adopted connection this fixture writes
        # through. Two threads on one sqlite connection interleave
        # transactions, which is an intermittent failure in whichever test
        # happens to be writing when a poll lands (#194).
        client.app.state.worker.stop()  # type: ignore[attr-defined]
        client.app.state.worker.join(timeout=5)  # type: ignore[attr-defined]
        browser = Browser(client, token, conn)
        browser.root, browser.leaves = root, (a, b, c)
        browser.elsewhere = d
        yield browser
    conn.close()


def test_the_default_graph_draws_no_overlay(browser: Browser) -> None:
    browser.sign_in()

    page = browser.map()

    assert 'class="link' not in page


def test_a_pull_edge_points_at_the_topic_that_is_nearer(
    browser: Browser,
) -> None:
    a, b, _ = browser.leaves

    pulls = browser.links("pull")

    assert [(link.source, link.target) for link in pulls] == [(a, b)]
    assert pulls[0].label == "1 chunk nearer"


def test_proximity_joins_near_siblings_and_not_distant_ones(
    browser: Browser,
) -> None:
    a, b, c = browser.leaves

    pairs = {(link.source, link.target) for link in browser.links("proximity")}

    assert pairs == {(b, c)}
    assert (a, b) not in pairs


def test_proximity_does_not_join_topics_under_different_parents(
    browser: Browser,
) -> None:
    """Near is not the same as adjacent, and the edge means "merge these".

    D sits on top of B and under another parent. Merging them would be a
    reparent as well as a merge, which is not what this edge offers.
    """
    _, b, c = browser.leaves
    d = browser.elsewhere

    pairs = {
        (link.source, link.target)
        for link in browser.links(
            "proximity", drawn=(browser.root, *browser.leaves, d)
        )
    }

    assert pairs == {(b, c)}


def test_the_candidate_set_is_what_is_drawn(browser: Browser) -> None:
    """A pull has to point somewhere the operator can look.

    D is nearer to A's stray chunk than B is, but D is not on the page. So B —
    the nearest topic that IS drawn — gets the edge, and computing centroids
    for the whole tree would silently hand it to a topic nobody can see.
    """
    a, b, _ = browser.leaves

    pulls = browser.links("pull")

    assert [(link.source, link.target) for link in pulls] == [(a, b)]


def test_a_propagation_edge_comes_from_the_update_log(
    browser: Browser,
) -> None:
    a, _, _ = browser.leaves
    with browser.conn:  # type: ignore[union-attr]
        record(browser.conn, TREE, a, "major", "propagated", browser.root)  # type: ignore[arg-type]

    links = browser.links("propagation")

    assert [(link.source, link.target) for link in links] == [(a, browser.root)]
    assert links[0].label == "propagated"


def test_an_edge_to_a_topic_that_is_not_drawn_is_dropped(
    browser: Browser,
) -> None:
    """The overlay describes what is DRAWN, and `?open=` decides that."""
    a, _, _ = browser.leaves
    with browser.conn:  # type: ignore[union-attr]
        record(browser.conn, TREE, a, "major", "propagated", browser.root)  # type: ignore[arg-type]
    browser.sign_in()

    # `open=` PRESENT and empty is what Collapse sends; absent now means a
    # first visit, which opens three levels (#197)
    collapsed = browser.client.get(
        f"/ui/trees/{TREE}/graph?open=&edges=propagation"
    ).text

    assert 'class="link' not in collapsed


def test_the_overlay_rides_in_the_url(browser: Browser) -> None:
    browser.sign_in()

    page = browser.map("pull")

    assert 'class="link pull"' in page
    # the toggle for one that is off ADDS it rather than replacing what is on
    assert "edges=pull,proximity" in page
    assert ">proximity<" in page  # and the legend names every kind


def test_two_overlays_at_once(browser: Browser) -> None:
    browser.sign_in()

    page = browser.map("pull,proximity")

    assert 'class="link pull"' in page
    assert 'class="link proximity"' in page


def test_without_an_embedding_model_the_tree_still_draws(
    browser: Browser,
) -> None:
    """A missing model is a DEGRADE, not a 500 — the map is still the map."""
    with browser.conn:  # type: ignore[union-attr]
        registry_store.delete(browser.conn, "models", MODEL)  # type: ignore[arg-type]
    browser.sign_in()

    page = browser.map("pull")

    assert "no embedding model available" in page
    assert "<svg" in page
    assert 'class="link' not in page


def test_an_unknown_edge_kind_is_ignored(browser: Browser) -> None:
    # a view cannot be invalid (#183): a hand-edited URL draws less, never 500
    browser.sign_in()

    answer = browser.client.get(f"/ui/trees/{TREE}/graph?edges=nonsense")

    assert answer.status_code == 200
    assert 'class="link' not in answer.text


def _embedding_reads(browser: Browser, url: str) -> int:
    """How many statements the page runs against the vector tables."""
    seen = 0

    def count(statement: str) -> None:
        nonlocal seen
        if "embeddings" in statement.lower():
            seen += 1

    browser.conn.set_trace_callback(count)  # type: ignore[attr-defined]
    try:
        browser.client.get(url)
    finally:
        browser.conn.set_trace_callback(None)  # type: ignore[attr-defined]
    return seen


def test_the_default_page_runs_no_vector_work(browser: Browser) -> None:
    """Off by default has to mean off, not computed-and-not-drawn.

    A centroid costs every member vector it is made of. Asserting that no link
    is DRAWN would leave the cost in place and say nothing about it.
    """
    browser.sign_in()
    url = f"/ui/trees/{TREE}/graph?open={browser.root}"

    assert _embedding_reads(browser, url) == 0
    assert _embedding_reads(browser, url + "&edges=pull") > 0


def test_propagation_alone_runs_no_vector_work(browser: Browser) -> None:
    # the one overlay that needs no model should not pay for the two that do
    browser.sign_in()
    url = f"/ui/trees/{TREE}/graph?open={browser.root}&edges=propagation"

    assert _embedding_reads(browser, url) == 0


def test_two_unparented_leaves_are_siblings_too(
    browser: Browser, tmp_path: Path
) -> None:
    """A tree with no level above it is every tree before the first brief pass.

    That is exactly where a near-duplicate cluster is worth seeing, and a rule
    that demanded a shared parent would draw nothing there — silently.
    """
    conn = open_database(tmp_path / "flat.db")
    registry_store.insert(conn, "models", MODEL, _model(), None, "t")
    with conn:
        register_path_bodies(conn, [PATH])
        upsert_vector(conn, content_hash(path_body(PATH)), MODEL, (1.0, 0.0))
        left = cluster_store.add_leaf_node(
            conn, TREE, [(_section(conn, "l", (1.0, 0.0)), False, None)]
        )
        right = cluster_store.add_leaf_node(
            conn, TREE, [(_section(conn, "r", (0.98, 0.2)), False, None)]
        )
        far = cluster_store.add_leaf_node(
            conn, TREE, [(_section(conn, "f", (-1.0, 0.0)), False, None)]
        )

    links = overlays.build(conn, TREE, (left, right, far), ("proximity",)).links

    assert [(link.source, link.target) for link in links] == [(left, right)]
    conn.close()
