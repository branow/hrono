"""E014: the map on a tree people actually build, not on nine topics.

On 132 topics with both overlays on, the arcs were a solid band, the names all
read "Handles assorted mat...", and the drawing ran off the window. The tree
here is the same shape: a root over twelve topics over ten leaves each, every
brief opening with the same words as a weak model writes them.
"""

from __future__ import annotations

import itertools
import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster import store as cluster_store
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.db.update_log import record
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.server import graph, labels, overlays
from hrono.server.app import create_app
from hrono.server.ui.views import ARC_CAP, _drawn_links, topic_boxes
from hrono.summarize import briefs

KEY = Fernet.generate_key()
TREE = "default"
GROUPS = 12
LEAVES = 10


class Scale:
    def __init__(
        self, conn: sqlite3.Connection, client: TestClient, token: str
    ) -> None:
        self.conn = conn
        self.client = client
        self.token = token
        self.root = 0
        self.uppers: list[int] = []
        self.leaves: list[list[int]] = []

    def drawn(self) -> graph.Graph:
        return graph.build(self.conn, TREE, [self.root, *self.uppers])

    def every_link(self, drawn: graph.Graph) -> overlays.Overlay:
        """A pull arc between every two neighbours on the leaf row, and one
        from each leaf up to its parent: far more than a person can read."""
        row = [node.id for node in drawn.nodes if node.level == 0]
        links = [
            overlays.Link("pull", a, b, "3 chunks nearer", weight=3.0)
            for a, b in itertools.pairwise(row)
        ]
        links += [
            overlays.Link("proximity", a, b, "0.88 similar", weight=0.88)
            for a, b in itertools.combinations(row[:14], 2)
        ]
        return overlays.Overlay(kinds=("pull", "proximity"), links=tuple(links))

    def across_levels(self, drawn: graph.Graph) -> overlays.Overlay:
        """Arcs between every two topics of the middle row, which has a row of
        words under it, and from the root down to every leaf, which has the
        middle row in the way."""
        middle = [node.id for node in drawn.nodes if node.level == 1]
        leaves = [node.id for node in drawn.nodes if node.level == 0]
        links = [
            overlays.Link("pull", a, b, "3 chunks nearer", weight=3.0)
            for a, b in itertools.combinations(middle, 2)
        ]
        links += [
            overlays.Link("propagation", self.root, leaf, "rewrote brief")
            for leaf in leaves
        ]
        return overlays.Overlay(
            kinds=("pull", "propagation"), links=tuple(links)
        )

    def page(self, query: str) -> str:
        return self.client.get(
            f"/ui/trees/{TREE}/graph?open={self.root},"
            f"{','.join(map(str, self.uppers))}&{query}"
        ).text


def _section(conn: sqlite3.Connection, path: str) -> int:
    body = f"{path} body\n".encode()
    istore.upsert_content(conn, content_hash(body), body)
    return istore.insert_section(
        conn,
        source="repo",
        address=Address("git", "ex/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=0,
    )


def _brief(conn: sqlite3.Connection, node: int, text: str) -> None:
    briefs.upsert(
        conn,
        node,
        text,
        model_name="m",
        prompt_name="brief",
        prompt_hash="h",
        member_signature="s",
        input_tokens=1,
        output_tokens=1,
    )


def _parent(conn: sqlite3.Connection, level: int, kids: list[int]) -> int:
    conn.execute(
        "INSERT INTO nodes(tree, level, label, created_at) "
        "VALUES (?, ?, 0, 't')",
        (TREE, level),
    )
    node = int(conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0])
    for kid in kids:
        cluster_store.add_child(
            conn, node, kid, attached=False, similarity=None
        )
    return node


@pytest.fixture(scope="module")
def scale(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Scale]:
    path: Path = tmp_path_factory.mktemp("scale") / "hrono.db"
    conn = open_database(path)
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    uppers: list[int] = []
    leaves: list[list[int]] = []
    with conn:
        for group in range(GROUPS):
            family = []
            for index in range(LEAVES):
                leaf = cluster_store.add_leaf_node(
                    conn,
                    TREE,
                    [
                        (
                            _section(conn, f"src/g{group}/m{index}.py"),
                            False,
                            None,
                        )
                    ],
                )
                _brief(
                    conn,
                    leaf,
                    f"Handles assorted material for the part {group}.{index}.",
                )
                family.append(leaf)
            upper = _parent(conn, 1, family)
            _brief(conn, upper, f"Handles assorted material for group {group}.")
            uppers.append(upper)
            leaves.append(family)
        root = _parent(conn, 2, uppers)
        _brief(conn, root, "Everything in the repository.")
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        app.state.worker.stop()
        app.state.worker.join(timeout=5)
        built = Scale(conn, client, token)
        built.root, built.uppers, built.leaves = root, uppers, leaves
        client.post("/ui/login", data={"token": token})
        yield built
    conn.close()


def _points(path: str) -> list[tuple[float, float]]:
    """A drawn arc's path, walked every few pixels, read from the PATH TEXT so
    the check does not share the code that chose it."""
    numbers = [float(n) for n in re.findall(r"-?\d+\.?\d*", path)]
    if "Q" in path:
        x1, y1, cx, cy, x2, y2 = numbers
        steps = int(abs(x2 - x1) / 3) + 20
        return [
            (
                (1 - t) ** 2 * x1 + 2 * t * (1 - t) * cx + t * t * x2,
                (1 - t) ** 2 * y1 + 2 * t * (1 - t) * cy + t * t * y2,
            )
            for t in (i / steps for i in range(steps + 1))
        ]
    x1, y1, x2, y2 = numbers
    return [
        (x1 + (x2 - x1) * t / 50, y1 + (y2 - y1) * t / 50) for t in range(51)
    ]


def test_the_tree_is_the_size_the_evidence_was(scale: Scale) -> None:
    assert len(scale.drawn().nodes) == 1 + GROUPS + GROUPS * LEAVES


def test_no_more_arcs_are_drawn_than_the_cap(scale: Scale) -> None:
    every = scale.drawn()
    overlay = scale.every_link(every)

    arcs = _drawn_links(overlay, every)

    assert len(overlay.links) > 3 * ARC_CAP
    assert 0 < len(arcs.drawn) <= ARC_CAP


def test_every_arc_left_out_is_counted_against_both_its_topics(
    scale: Scale,
) -> None:
    every = scale.drawn()
    overlay = scale.every_link(every)

    arcs = _drawn_links(overlay, every)

    assert sum(arcs.unseen.values()) == 2 * (
        len(overlay.links) - len(arcs.drawn)
    )


@pytest.mark.parametrize("shape", ["along-a-row", "across-levels"])
def test_no_drawn_arc_runs_through_a_topics_words(
    scale: Scale, shape: str
) -> None:
    every = scale.drawn()
    overlay = (
        scale.every_link(every)
        if shape == "along-a-row"
        else scale.across_levels(every)
    )
    arcs = _drawn_links(overlay, every)
    boxes = topic_boxes(every)

    assert arcs.drawn
    for arc in arcs.drawn:
        for x, y in _points(str(arc["d"])):
            for box in boxes:
                inside = box.left < x < box.right and box.top < y < box.bottom
                assert not inside, (arc["d"], box)


def test_no_arc_runs_through_another_arcs_label_in_a_fan(
    scale: Scale,
) -> None:
    every = scale.drawn()
    uppers = [node.id for node in every.nodes if node.level == 1]
    leaves = [node.id for node in every.nodes if node.level == 0]
    overlay = overlays.Overlay(
        kinds=("propagation",),
        links=tuple(
            overlays.Link("propagation", scale.root, end, "propagated")
            for end in [*uppers, *leaves[:: len(leaves) // 8]]
        ),
    )

    arcs = _drawn_links(overlay, every)

    assert len(arcs.drawn) >= 8
    for arc in arcs.drawn:
        box = labels.text(
            float(str(arc["x"])),
            float(str(arc["y"])),
            str(arc["label"]),
            labels.META_CHAR,
        )
        for other in arcs.drawn:
            if other is arc:
                continue
            for x, y in _points(str(other["d"])):
                inside = box.left < x < box.right and box.top < y < box.bottom
                assert not inside, (other["d"], arc["label"], box)


def test_the_cap_keeps_the_strongest_of_EACH_kind() -> None:
    pulls = [
        overlays.Link("pull", i, i + 1, "n", weight=float(i)) for i in range(30)
    ]
    near = [overlays.Link("proximity", 100, 101, "0.71 similar", weight=0.71)]

    kept = overlays.strongest([*pulls, *near], 4)

    assert near[0] in kept
    assert [link.weight for link in kept if link.kind == "pull"] == [
        29.0,
        28.0,
        27.0,
    ]


def test_a_topic_with_arcs_left_out_says_how_many_and_opens_them(
    scale: Scale,
) -> None:
    row = scale.leaves[0]
    with scale.conn:
        for first, second in itertools.pairwise(row):
            record(scale.conn, TREE, first, "major", "propagated", second)
        for leaf in scale.leaves[1]:
            record(scale.conn, TREE, leaf, "major", "propagated", row[0])

    page = scale.page("edges=propagation")
    chips = re.findall(
        r'<a href="([^"]+)" class="more">\s*<text[^>]*>([^<]+)', page
    )
    drawn_arcs = re.findall(r'<path d="[^"]+" class="link', page)

    assert len(drawn_arcs) <= ARC_CAP
    assert chips, "arcs were left out and nothing says so"
    href = next(
        href.replace("&amp;", "&")
        for href, _ in chips
        if f"arcs={row[0]}" in href
    )
    alone = scale.client.get(href).text
    mine = re.findall(r'<path d="[^"]+" class="link', alone)
    assert 0 < len(mine) <= ARC_CAP
    assert "Only this topic" in alone  # and the way back to the whole map


def test_a_chip_sits_clear_of_every_topics_words(scale: Scale) -> None:
    every = scale.drawn()
    arcs = _drawn_links(scale.every_link(every), every)
    chips = graph_chips(scale, every, arcs.unseen)

    boxes = topic_boxes(every)
    assert chips
    for chip in chips:
        width = len(str(chip["text"])) * labels.META_CHAR
        x, y = float(chip["x"]), float(chip["y"])
        shape = labels.Box(x, y - labels.ASCENT, x + width, y + labels.DESCENT)
        assert not any(shape.hits(box) for box in boxes), chip


def graph_chips(
    scale: Scale, every: graph.Graph, unseen: dict[int, int]
) -> list[dict[str, object]]:
    from hrono.server.ui.views import _chips

    return _chips(every, unseen, TREE, "", "pull", "")


def test_siblings_that_open_alike_are_told_apart_by_what_follows(
    scale: Scale,
) -> None:
    shown = [
        node.label for node in scale.drawn().nodes if node.id in scale.leaves[3]
    ]

    assert len(set(shown)) == LEAVES, shown
    assert all(len(label) <= graph.TITLE_CHARS for label in shown)
    assert all(".".join(["3", str(i)]) in shown[i] for i in range(LEAVES)), (
        shown
    )


def test_a_name_that_fits_is_left_alone(scale: Scale) -> None:
    root = next(n for n in scale.drawn().nodes if n.id == scale.root)

    assert root.label == root.name


def test_a_row_wider_than_the_window_has_a_way_to_the_rest(
    scale: Scale,
) -> None:
    page = scale.page("")

    assert 'id="beyond-left"' in page
    assert 'id="beyond-right"' in page


def test_links_under_the_cap_keep_the_order_they_were_found_in() -> None:
    found = [
        overlays.Link("proximity", 1, 2, "a", weight=0.9),
        overlays.Link("pull", 1, 2, "b", weight=5.0),
        overlays.Link("pull", 3, 4, "c", weight=1.0),
    ]

    assert overlays.strongest(found, 3) == tuple(found)
