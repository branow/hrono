"""Laying a tree out for the page (T50.1/.2, #183).

Arithmetic, not a library. A hierarchy drawn level by level is positions and
line segments, and SVG is markup — so the graph is rendered by the same Jinja
that renders everything else, with no JS dependency to vendor, review and pin.

The expand state is a QUERY PARAMETER rather than client state, which is what
makes every view of the graph a URL: bookmarkable, shareable, and testable as
HTML rather than as a screenshot.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

# Room for a label under each node without the columns colliding on a wide
# level; the page scrolls sideways rather than shrinking the nodes to dots.
COLUMN = 150
ROW = 110
MARGIN = 40
MIN_RADIUS = 10
MAX_RADIUS = 26


@dataclass(frozen=True)
class Node:
    """One drawn topic and everything the page needs to draw it."""

    id: int
    level: int
    title: str
    holds: int  # members for a leaf, children for an upper topic
    stale: bool
    has_hidden_children: bool
    x: float
    y: float
    radius: float


@dataclass(frozen=True)
class Graph:
    nodes: tuple[Node, ...]
    edges: tuple[tuple[float, float, float, float], ...]
    width: float
    height: float


def build(conn: sqlite3.Connection, tree: str, opened: Sequence[int]) -> Graph:
    """Draw the root, and the children of every OPEN topic below it."""
    rows = _rows(conn, tree)
    if not rows:
        return Graph(nodes=(), edges=(), width=0, height=0)
    children = _children(conn, tree)
    roots = _roots(rows, children)
    visible = _visible(roots, children, set(opened))
    return _lay_out(rows, children, visible, set(opened))


def _rows(conn: sqlite3.Connection, tree: str) -> dict[int, sqlite3.Row]:
    return {
        int(row["id"]): row
        for row in conn.execute(
            "SELECT n.id AS id, n.level AS level, n.title AS title, "
            "b.text AS brief, COALESCE(b.stale, 0) AS stale, "
            "(SELECT COUNT(*) FROM node_members m WHERE m.node_id = n.id) "
            "AS members, "
            "(SELECT COUNT(*) FROM node_children c WHERE c.parent_id = n.id) "
            "AS kids "
            "FROM nodes n LEFT JOIN briefs b ON b.node_id = n.id "
            "WHERE n.tree = ? ORDER BY n.id",
            (tree,),
        ).fetchall()
    }


def _children(conn: sqlite3.Connection, tree: str) -> dict[int, list[int]]:
    edges: dict[int, list[int]] = {}
    for row in conn.execute(
        "SELECT c.parent_id AS parent, c.child_id AS child "
        "FROM node_children c JOIN nodes n ON n.id = c.parent_id "
        "WHERE n.tree = ? "
        "ORDER BY c.parent_id, c.child_id",
        (tree,),
    ).fetchall():
        edges.setdefault(int(row["parent"]), []).append(int(row["child"]))
    return edges


def _roots(
    rows: dict[int, sqlite3.Row], children: dict[int, list[int]]
) -> list[int]:
    """The topics nothing points at — normally one, but never assume it.

    A tree mid-repair can have more than one, and drawing only the first would
    hide exactly the state an operator opened the graph to find (#124, #163).
    """
    parented = {child for kids in children.values() for child in kids}
    return [node for node in rows if node not in parented]


def _visible(
    roots: Sequence[int],
    children: dict[int, list[int]],
    opened: set[int],
) -> list[int]:
    """Depth-first, descending only through OPEN topics."""
    order: list[int] = []
    frontier = list(reversed(roots))
    while frontier:
        node = frontier.pop()
        order.append(node)
        if node in opened:
            frontier.extend(reversed(children.get(node, [])))
    return order


def _lay_out(
    rows: dict[int, sqlite3.Row],
    children: dict[int, list[int]],
    visible: Sequence[int],
    opened: set[int],
) -> Graph:
    """One column per visible topic, one row per level.

    Column order follows the depth-first walk, so a topic's descendants sit to
    its right and a branch reads as a block.
    """
    top = max(int(rows[node]["level"]) for node in visible)
    holds = {node: _holds(rows[node]) for node in visible}
    biggest = max(holds.values(), default=1) or 1
    placed: dict[int, tuple[float, float]] = {}
    drawn: list[Node] = []
    for column, node in enumerate(visible):
        row = rows[node]
        x = MARGIN + column * COLUMN
        y = MARGIN + (top - int(row["level"])) * ROW
        placed[node] = (x, y)
        kids = children.get(node, [])
        drawn.append(
            Node(
                id=node,
                level=int(row["level"]),
                title=_title(row, node),
                holds=holds[node],
                stale=bool(row["stale"]) or row["brief"] is None,
                has_hidden_children=bool(kids) and node not in opened,
                x=x,
                y=y,
                radius=MIN_RADIUS
                + (MAX_RADIUS - MIN_RADIUS) * (holds[node] / biggest),
            )
        )
    edges = tuple(
        (*placed[parent], *placed[child])
        for parent in visible
        for child in children.get(parent, [])
        if child in placed
    )
    return Graph(
        nodes=tuple(drawn),
        edges=edges,
        width=MARGIN * 2 + max(len(visible) - 1, 0) * COLUMN,
        height=MARGIN * 2 + top * ROW,
    )


def _holds(row: sqlite3.Row) -> int:
    """What a topic contains: chunks at the leaves, topics above them.

    One number for two kinds, because the question the size answers is "how
    much is under here", and an upper node's members are always zero (#163).
    """
    return int(row["members"]) or int(row["kids"])


def _title(row: sqlite3.Row, node: int) -> str:
    if row["title"]:
        return str(row["title"])
    if row["brief"]:
        return str(row["brief"]).strip().splitlines()[0][:28]
    return f"topic {node}"
