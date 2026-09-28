"""Laying a tree out for the page (T50.1/.2, #183).

Arithmetic, not a library. A hierarchy drawn level by level is positions and
line segments, and SVG is markup — so the graph is rendered by the same Jinja
that renders everything else, with no JS dependency to vendor, review and pin.

The layout is a DENDROGRAM: levels run left to right, siblings stack downwards,
a parent sits centred on its visible children, and every label is left-anchored
beside its own topic. The earlier layout gave each visible topic a COLUMN, so a
tree of 26 leaves was 4,000px of horizontal scroll and every label was clipped
to 20 characters — twenty-six topics that all began "This group covers…" read as
one repeated word. Stacking downwards costs a page scroll, which browsers are
built for, and buys a label the width of the canvas.

The expand state is a QUERY PARAMETER rather than client state, which is what
makes every view of the graph a URL: bookmarkable, shareable, and testable as
HTML rather than as a screenshot.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

# One level per column, one topic per row. ROW carries two lines of text (the
# name and what the topic holds), so it cannot go below ~36.
COLUMN = 260
ROW = 40
# Room on the left for the disclosure triangle, which sits outside the circle.
LEFT = 40
TOP = 30
# Room on the right of the LAST column for that column's labels.
LABEL_WIDTH = 240
# A label must fit inside its column or it collides with the next column's
# circles. COLUMN is 260px, the label font is 12px (~6.6px a character) and the
# circle eats ~30px, so ~32 characters is the budget.
LABEL_CHARS = 32
MIN_RADIUS = 5
MAX_RADIUS = 15
# Where a parent's children hang. It sits in the gutter between the parent's
# circle and the start of its label: a trunk drawn half-way to the child column
# instead would cross the parent's own name on its way there.
TRUNK_GAP = 20


@dataclass(frozen=True)
class Node:
    """One drawn topic and everything the page needs to draw it."""

    id: int
    level: int
    title: str
    holds: int  # members for a leaf, children for an upper topic
    holds_what: str  # "chunks" or "topics" — the unit `holds` counts
    stale: bool
    has_children: bool
    has_hidden_children: bool
    x: float
    y: float
    radius: float


@dataclass(frozen=True)
class Graph:
    """A drawn tree: placed nodes, connector paths, and the canvas they need.

    ``edges`` is SVG path data rather than endpoints because the connector is
    an elbow, not a segment: a parent drops one trunk and each child branches
    off it, which is what makes a column of circles read as one family.
    """

    nodes: tuple[Node, ...]
    edges: tuple[str, ...]
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
    """One column per LEVEL, one row per drawn topic.

    A topic with no drawn children takes the next free row; a topic with them
    sits at their average, so a parent is always beside the block it owns.
    """
    top = max(int(rows[node]["level"]) for node in visible)
    shown = set(visible)
    drawn_kids = {
        node: [kid for kid in children.get(node, []) if kid in shown]
        for node in visible
    }
    slots = _slots(visible, drawn_kids)
    holds = {node: _holds(rows[node]) for node in visible}
    biggest = max(holds.values(), default=1) or 1
    placed = {
        node: (
            LEFT + (top - int(rows[node]["level"])) * COLUMN,
            TOP + slots[node] * ROW,
        )
        for node in visible
    }
    drawn = tuple(
        Node(
            id=node,
            level=int(rows[node]["level"]),
            title=_title(rows[node], node),
            holds=holds[node],
            holds_what=_holds_what(rows[node]),
            stale=bool(rows[node]["stale"]) or rows[node]["brief"] is None,
            has_children=bool(children.get(node)),
            has_hidden_children=bool(children.get(node)) and node not in opened,
            x=placed[node][0],
            y=placed[node][1],
            radius=_radius(holds[node], biggest),
        )
        for node in visible
    )
    edges = tuple(
        _elbow(*placed[parent], *placed[child])
        for parent in visible
        for child in drawn_kids[parent]
    )
    return Graph(
        nodes=drawn,
        edges=edges,
        width=LEFT + top * COLUMN + LABEL_WIDTH,
        height=TOP * 2 + max(slots.values(), default=0) * ROW,
    )


def _slots(
    visible: Sequence[int], drawn_kids: dict[int, list[int]]
) -> dict[int, float]:
    """Give every drawn topic a row: leaves in order, parents on their block.

    ``visible`` is depth-first pre-order, so walking it BACKWARDS meets every
    child before its parent and one pass suffices.
    """
    rank = {
        node: float(index)
        for index, node in enumerate(
            node for node in visible if not drawn_kids[node]
        )
    }
    for node in reversed(visible):
        kids = drawn_kids[node]
        if kids:
            rank[node] = sum(rank[kid] for kid in kids) / len(kids)
    return rank


def _elbow(x1: float, y1: float, x2: float, y2: float) -> str:
    """A parent-to-child connector: out to the trunk, along it, then in."""
    return f"M{x1},{y1} H{x1 + TRUNK_GAP} V{y2} H{x2}"


def _radius(holds: int, biggest: int) -> float:
    """Area, not radius, follows what a topic holds.

    A circle is read by its area, so scaling the radius linearly makes a topic
    of thirty chunks look nine times the one of ten rather than three.
    """
    share = (holds / biggest) ** 0.5 if biggest else 0.0
    return round(MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * share, 1)


def _holds(row: sqlite3.Row) -> int:
    """What a topic contains: chunks at the leaves, topics above them.

    One number for two kinds, because the question the size answers is "how
    much is under here", and an upper node's members are always zero (#163).
    """
    return int(row["members"]) or int(row["kids"])


def _holds_what(row: sqlite3.Row) -> str:
    """The unit `_holds` counted, so the page says it rather than implies it."""
    return "chunks" if int(row["members"]) else "topics"


def _title(row: sqlite3.Row, node: int) -> str:
    if row["title"]:
        return _fitted(str(row["title"]))
    if row["brief"]:
        return _fitted(str(row["brief"]).strip().splitlines()[0])
    return f"topic {node}"


def _fitted(text: str) -> str:
    """Cut a label to its column, with an ellipsis so the cut is visible."""
    if len(text) <= LABEL_CHARS:
        return text
    return text[: LABEL_CHARS - 1].rstrip(" ,;:.") + "…"
