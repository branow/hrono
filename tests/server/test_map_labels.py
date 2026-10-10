"""Names you can tell apart, and no word on the map over another."""

import itertools
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono import naming
from hrono.cluster import store as cluster_store
from hrono.db.database import open_database
from hrono.export.collapse import collapse
from hrono.export.render import render
from hrono.export.store import load
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.server import graph, labels, overlays
from hrono.server.ui.views import ARC_CAP, _drawn_links, topic_boxes
from hrono.summarize import briefs

TREE = "default"
WEAK = "This topic covers the module's API and how its parts fit together."


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


@pytest.fixture
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A root over 9 topics under 3 parents; every brief opens the same way,
    as a weak model writes them, except one parent's children."""
    connection = open_database(tmp_path / "hrono.db")
    with connection:
        uppers = []
        for u in range(3):
            leaves = []
            for i in range(3):
                leaf = cluster_store.add_leaf_node(
                    connection,
                    TREE,
                    [
                        (
                            _section(connection, f"src/m{u}/f{i}_{k}.py"),
                            False,
                            None,
                        )
                        for k in range(1 + i)
                    ],
                )
                _brief(connection, leaf, WEAK if u else f"Parser number {i}.")
                leaves.append(leaf)
            connection.execute(
                "INSERT INTO nodes(tree, level, label, created_at) "
                "VALUES (?, 1, ?, 't')",
                (TREE, u),
            )
            upper = int(
                connection.execute("SELECT MAX(id) FROM nodes").fetchone()[0]
            )
            for leaf in leaves:
                cluster_store.add_child(
                    connection, upper, leaf, attached=False, similarity=None
                )
            _brief(connection, upper, WEAK)
            uppers.append(upper)
        connection.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, 2, 0, 't')",
            (TREE,),
        )
        root = int(
            connection.execute("SELECT MAX(id) FROM nodes").fetchone()[0]
        )
        for upper in uppers:
            cluster_store.add_child(
                connection, root, upper, attached=False, similarity=None
            )
        _brief(connection, root, "Everything in the repository.")
    yield connection
    connection.close()


def _siblings(conn: sqlite3.Connection) -> list[list[int]]:
    rows = conn.execute(
        "SELECT parent_id, child_id FROM node_children ORDER BY child_id"
    ).fetchall()
    families: dict[int, list[int]] = {}
    for row in rows:
        families.setdefault(int(row[0]), []).append(int(row[1]))
    return list(families.values())


def test_no_two_siblings_read_the_same(conn: sqlite3.Connection) -> None:
    ids = [int(r[0]) for r in conn.execute("SELECT id FROM nodes")]
    called = naming.names(conn, ids)

    for family in _siblings(conn):
        shown = [called[node] for node in family]
        assert len(set(shown)) == len(shown), shown
    # a title nobody else under the parent has is left alone
    assert "Parser number 1." in called.values()


def test_a_name_survives_being_cut_to_its_slot(
    conn: sqlite3.Connection,
) -> None:
    drawn = graph.build(conn, TREE, [n for f in _siblings(conn) for n in f])

    for family in _siblings(conn):
        shown = [node.label for node in drawn.nodes if node.id in family]
        assert len(set(shown)) == len(shown), shown
        assert all(len(label) <= graph.LABEL_CHARS for label in shown)


def test_the_map_and_the_export_call_a_topic_the_same(
    conn: sqlite3.Connection,
) -> None:
    files = render(conn, collapse(load(conn, TREE), 3))  # type: ignore[arg-type]
    root = int(
        conn.execute("SELECT id FROM nodes WHERE level = 2").fetchone()[0]
    )
    uppers = [
        int(r[0])
        for r in conn.execute(
            "SELECT child_id FROM node_children WHERE parent_id = ?", (root,)
        )
    ]

    called = naming.names(conn, uppers)
    for upper in uppers:
        assert f"- [{called[upper]}](" in files["root.md"]


def test_with_every_overlay_no_word_lands_on_another(
    conn: sqlite3.Connection,
) -> None:
    opened = [n for f in _siblings(conn) for n in f] + [
        int(r[0]) for r in conn.execute("SELECT id FROM nodes WHERE level = 2")
    ]
    drawn = graph.build(conn, TREE, opened)
    ids = [node.id for node in drawn.nodes]
    links = tuple(
        overlays.Link(kind, a, b, label)
        for (a, b), (kind, label) in zip(
            itertools.combinations(ids, 2),
            itertools.cycle(
                [
                    ("pull", "4 sections"),
                    ("proximity", "0.88 similar"),
                    ("propagation", "rewrote brief"),
                ]
            ),
            strict=False,
        )
    )
    overlay = overlays.Overlay(kinds=overlays.KINDS, links=links)

    arcs = _drawn_links(overlay, drawn)
    placed = arcs.drawn

    words = [
        labels.text(link["x"], link["y"], link["label"], labels.META_CHAR)
        for link in placed
    ]
    topics = topic_boxes(drawn)
    assert 0 < len(placed) <= ARC_CAP < len(links)
    for one, other in itertools.combinations(words, 2):
        assert not one.hits(other), (one, other)
    for word in words:
        assert not any(word.hits(box) for box in topics), word
    names = [box for box in topics if box.bottom - box.top < 20]
    for one, other in itertools.combinations(names, 2):
        assert not one.hits(other), (one, other)


def test_names_that_differ_only_past_the_slot_are_told_apart(
    conn: sqlite3.Connection,
) -> None:
    leaves = [
        int(r[0])
        for r in conn.execute(
            "SELECT child_id FROM node_children WHERE parent_id = "
            "(SELECT MIN(id) FROM nodes WHERE level = 1) ORDER BY child_id"
        )
    ]
    with conn:
        for leaf, end in zip(
            leaves, ("tests", "errors", "fixtures"), strict=True
        ):
            _brief(
                conn, leaf, f"Handles the configuration parser and its {end}."
            )
    every = [int(r[0]) for r in conn.execute("SELECT id FROM nodes")]

    drawn = graph.build(conn, TREE, every)

    shown = [node.label for node in drawn.nodes if node.id in leaves]
    assert len(set(shown)) == 3, shown
    assert all(len(label) <= graph.LABEL_CHARS for label in shown)


def test_an_arc_leaves_a_topic_clear_of_its_words(
    conn: sqlite3.Connection,
) -> None:
    """Under its words for a topic in a row; out of the circle's left side,
    away from the words, for a leaf in a stack."""
    every = [int(r[0]) for r in conn.execute("SELECT id FROM nodes")]
    drawn = graph.build(conn, TREE, every)
    row = [node for node in drawn.nodes if node.level == 0]
    links = tuple(
        overlays.Link("pull", a.id, b.id, "1 section")
        for a, b in zip(row, row[1:], strict=False)
    )

    placed = _drawn_links(overlays.Overlay(("pull",), links), drawn).drawn
    assert placed

    nodes = {node.id: node for node in row}
    for drawn_link in placed:
        x, y = (
            float(part)
            for part in str(drawn_link["d"]).split()[0][1:].split(",")
        )
        source = next(
            node
            for node in row
            if abs(node.y - y) <= node.radius + 80
            and abs(node.x - x) <= node.radius + 80
        )
        words = labels.topic(
            source.x,
            source.y,
            source.radius,
            (source.label, source.place, f"{source.holds} {source.holds_what}"),
            source.has_children,
            graph.BESIDE if source.beside else 0.0,
        )
        assert not any(
            box.left <= x <= box.right and box.top <= y <= box.bottom
            for box in words
        ), (drawn_link["d"], nodes)
