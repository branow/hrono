"""Laying a tree out for the page (T50.1/.2, #183, #198).

Arithmetic, not a library. A hierarchy drawn level by level is positions and
line segments, and SVG is markup — so the graph is rendered by the same Jinja
that renders everything else, with no JS dependency to vendor, review and pin.

The layout is a TOP-DOWN TREE of BLOCKS: the root sits at the top, its
children hang below it, and a topic with more children than fit across the
page wraps them onto further rows rather than running off the edge. It was a
left-to-right dendrogram until #198 — the shape a file explorer has, which
nobody reads as a tree — and then one row per level, which put twenty-six
siblings across four thousand pixels and three screenfuls. A block fits the
page, so the whole map is one screen and the root is the first thing on it.

Each topic is labelled by WHERE its sections live (`server/where.py`) rather
than by its brief's first line: on a tree summarised by a weak model every
brief opens with the same clause, and twenty-six identical labels are not a
map. The brief-derived name stays as the secondary identity, on hover and on
the topic page.

The expand state is a QUERY PARAMETER rather than client state, which is what
makes every view of the graph a URL: bookmarkable, shareable, and testable as
HTML rather than as a screenshot.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from hrono.server import where as where_module

# A topic's own footprint: one cell wide, with its circle at the top and its
# two lines of text centred under it.
SLOT = 150
# The widest a row of children may be before it WRAPS onto another row. The
# canvas is a width the server picks, so it is chosen for the narrowest window
# this dashboard is drawn for — 1100px, less main's padding and the gutter a
# wrapped block keeps down its left side.
ROW_WIDTH = 1000
# Vertical room a topic's own furniture needs below the top of its cell: the
# circle, its name, its count. A topic that can be opened carries a chevron
# under those.
NODE_HEIGHT = 68
CHEVRON = 18
# Between a parent's furniture and its children, and between two wrapped rows
# of them.
DROP = 30
ROW_GAP = 16
# Down the left of a block that wrapped: the spine joining its rows runs here,
# clear of every label.
GUTTER = 24
# Half a label either side of the drawing, so no name is cut by the canvas.
PAD = 20
TOP = 10
BOTTOM = 8
# A label must fit inside its slot or it collides with its neighbour's and is
# cut by the canvas edge. The label font is 11.5px mono, ~6.9px a character,
# so 18 of them fit a 150px slot with a gutter to spare.
LABEL_CHARS = 18
LABEL_CHAR = 6.9
LABEL_WIDTH = LABEL_CHARS * LABEL_CHAR
# The brief-derived name is only ever read in a tooltip, where a long line
# wraps badly.
TITLE_CHARS = 56
MIN_RADIUS = 6
MAX_RADIUS = 18
# The radius of the rounded corner where a connector turns.
TURN = 8


@dataclass(frozen=True)
class Node:
    """One drawn topic and everything the page needs to draw it."""

    id: int
    level: int
    where: str  # the directory its sections live in — its primary identity
    label: str  # `where`, cut to fit its slot
    title: str  # what its brief calls it, for the tooltip and the topic page
    holds: int  # members for a leaf, children for an upper topic
    holds_what: str  # "sections" or "topics" — the unit `holds` counts
    stale: bool
    has_children: bool
    has_hidden_children: bool
    x: float
    y: float
    radius: float


@dataclass(frozen=True)
class Connector:
    """One drawn connection, and whether it had to travel past other topics.

    A connector to a WRAPPED row cannot go straight down — the rows above it
    are in the way — so it steps out, drops, and comes back. Three long runs
    with rounded corners draw what looks like a box around whatever they pass,
    and a box asserts a grouping the tree does not have. Marking the detour
    lets it be drawn as subordinate: the eye reads it as a line going by,
    not as a container (#197).
    """

    d: str
    past: bool


@dataclass(frozen=True)
class Graph:
    """A drawn tree: placed nodes, connector paths, and the canvas they need.

    ``edges`` is SVG path data rather than endpoints because a connector is a
    run of right angles, not a segment: out of the parent, along the row its
    children sit on, and down into each of them.
    """

    nodes: tuple[Node, ...]
    edges: tuple[Connector, ...]
    width: float
    height: float


@dataclass(frozen=True)
class _Box:
    """What one topic and everything drawn beneath it occupies.

    ``rows`` is how its children were WRAPPED — measuring and placing have to
    agree about that, so it is decided once, here, and carried.
    """

    width: float
    height: float
    rows: tuple[tuple[int, ...], ...]


def build(conn: sqlite3.Connection, tree: str, opened: Sequence[int]) -> Graph:
    """Draw the root, and the children of every OPEN topic below it."""
    rows = _rows(conn, tree)
    if not rows:
        return Graph(nodes=(), edges=(), width=0, height=0)
    children = _children(conn, tree)
    roots = _roots(rows, children)
    visible = _visible(roots, children, set(opened))
    return _lay_out(
        rows, children, visible, set(opened), where_module.by_node(conn, tree)
    )


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
    wheres: dict[int, str],
) -> Graph:
    """A block per topic: its own row, then its children WRAPPED beneath it.

    One row per level would be a level of twenty-six topics four thousand
    pixels wide — a map read in three screenfuls (#198). Children are packed
    into as many rows as ROW_WIDTH allows instead, so a topic and everything
    under it is a block that fits the page, and the tree still hangs
    downwards.
    """
    shown = set(visible)
    drawn_kids = {
        node: [kid for kid in children.get(node, []) if kid in shown]
        for node in visible
    }
    holds = {node: _holds(rows[node]) for node in visible}
    biggest = max(holds.values(), default=1) or 1
    radii = {node: _radius(holds[node], biggest) for node in visible}
    tall = {node: _own_height(bool(children.get(node))) for node in visible}
    boxes = _boxes(visible, drawn_kids, tall)
    placed, edges, width, height = _place(
        _drawn_roots(visible, drawn_kids), boxes, drawn_kids, radii, tall
    )
    drawn = tuple(
        Node(
            id=node,
            level=int(rows[node]["level"]),
            where=wheres.get(node, ""),
            label=_fitted_where(wheres.get(node, "")) or f"topic {node}",
            title=_title(rows[node], node),
            holds=holds[node],
            holds_what=_holds_what(rows[node]),
            stale=bool(rows[node]["stale"]) or rows[node]["brief"] is None,
            has_children=bool(children.get(node)),
            has_hidden_children=bool(children.get(node)) and node not in opened,
            x=placed[node][0],
            y=placed[node][1],
            radius=radii[node],
        )
        for node in visible
    )
    return Graph(nodes=drawn, edges=edges, width=width, height=height)


def _drawn_roots(
    visible: Sequence[int], drawn_kids: dict[int, list[int]]
) -> list[int]:
    hung = {kid for kids in drawn_kids.values() for kid in kids}
    return [node for node in visible if node not in hung]


def _own_height(has_children: bool) -> float:
    return NODE_HEIGHT + (CHEVRON if has_children else 0)


def _boxes(
    visible: Sequence[int],
    drawn_kids: dict[int, list[int]],
    tall: dict[int, float],
) -> dict[int, _Box]:
    """Measure every topic bottom-up: a parent cannot be sized before its kids.

    ``visible`` is depth-first pre-order, so walking it BACKWARDS meets every
    child before its parent and one pass suffices.
    """
    boxes: dict[int, _Box] = {}
    for node in reversed(visible):
        kids = drawn_kids[node]
        if not kids:
            boxes[node] = _Box(SLOT, tall[node], ())
            continue
        rows = _wrapped(kids, boxes)
        inside = max(_row_width(row, boxes) for row in rows)
        gutter = GUTTER if len(rows) > 1 else 0.0
        boxes[node] = _Box(
            width=max(SLOT, inside + gutter),
            height=tall[node] + DROP + _rows_height(rows, boxes),
            rows=rows,
        )
    return boxes


def _wrapped(
    kids: Sequence[int], boxes: dict[int, _Box]
) -> tuple[tuple[int, ...], ...]:
    """Pack children into rows no wider than ROW_WIDTH, in order.

    A child wider than the budget still gets a row — wrapping it away would
    lose it, and a block that big is already the widest thing on the page.
    """
    rows: list[tuple[int, ...]] = []
    row: list[int] = []
    used = 0.0
    for kid in kids:
        if row and used + boxes[kid].width > ROW_WIDTH:
            rows.append(tuple(row))
            row, used = [], 0.0
        row.append(kid)
        used += boxes[kid].width
    rows.append(tuple(row))
    return tuple(rows)


def _row_width(row: Sequence[int], boxes: dict[int, _Box]) -> float:
    return sum(boxes[node].width for node in row)


def _rows_height(
    rows: Sequence[Sequence[int]], boxes: dict[int, _Box]
) -> float:
    tallest = [max(boxes[node].height for node in row) for row in rows]
    return sum(tallest) + ROW_GAP * (len(rows) - 1)


def _place(
    roots: Sequence[int],
    boxes: dict[int, _Box],
    drawn_kids: dict[int, list[int]],
    radii: dict[int, float],
    tall: dict[int, float],
) -> tuple[dict[int, tuple[float, float]], tuple[str, ...], float, float]:
    """Walk the blocks top-down, placing each and drawing what joins them."""
    rows = _wrapped(roots, boxes)
    spread = max(_row_width(row, boxes) for row in rows)
    placed: dict[int, tuple[float, float]] = {}
    edges: list[Connector] = []
    stack = list(_laid(rows, boxes, PAD, spread, TOP))
    while stack:
        node, left, top = stack.pop()
        box = boxes[node]
        placed[node] = (left + box.width / 2, top + MAX_RADIUS)
        if not box.rows:
            continue
        gutter = GUTTER if len(box.rows) > 1 else 0.0
        foot = top + tall[node]
        kids = list(
            _laid(
                box.rows, boxes, left + gutter, box.width - gutter, foot + DROP
            )
        )
        edges.extend(
            _connectors(
                parent=placed[node],
                foot=foot,
                rows=box.rows,
                kids={
                    kid: (kid_left, kid_top) for kid, kid_left, kid_top in kids
                },
                boxes=boxes,
                radii=radii,
            )
        )
        stack.extend(kids)
    return (
        placed,
        tuple(edges),
        spread + PAD * 2,
        TOP + _rows_height(rows, boxes) + BOTTOM,
    )


def _laid(
    rows: Sequence[Sequence[int]],
    boxes: dict[int, _Box],
    left: float,
    width: float,
    top: float,
) -> list[tuple[int, float, float]]:
    """Give every topic in a wrapped block its own corner, row by row.

    Each row is CENTRED in the block, so a last row of two under a full row of
    six reads as part of the same family rather than as a stray.
    """
    out: list[tuple[int, float, float]] = []
    for row in rows:
        x = left + (width - _row_width(row, boxes)) / 2
        for node in row:
            out.append((node, x, top))
            x += boxes[node].width
        top += max(boxes[node].height for node in row) + ROW_GAP
    return out


def _connectors(
    parent: tuple[float, float],
    foot: float,
    rows: Sequence[Sequence[int]],
    kids: dict[int, tuple[float, float]],
    boxes: dict[int, _Box],
    radii: dict[int, float],
) -> list[Connector]:
    """One path per child, so a connector is never a line to nowhere.

    The first row hangs straight off the parent. A row below it is reached by
    a line that goes DOWN PAST the rows above it — never between them, where
    it would be read through their names.
    """
    out: list[Connector] = []
    bus = foot + DROP / 2
    for index, row in enumerate(rows):
        left, top = kids[row[0]]
        rail = top - ROW_GAP / 2 if index else bus
        past = _past(rows[:index], kids) if index else 0.0
        for kid in row:
            left, top = kids[kid]
            x = left + boxes[kid].width / 2
            turn = (
                [(parent[0], bus)]
                if index == 0
                else [
                    (parent[0], bus),
                    (past, bus),
                    (past, rail),
                ]
            )
            out.append(
                Connector(
                    d=_path(
                        [
                            (parent[0], foot),
                            *turn,
                            (x, rail),
                            (x, top + MAX_RADIUS - radii[kid]),
                        ]
                    ),
                    past=index > 0,
                )
            )
    return out


def _past(
    above: Sequence[Sequence[int]], kids: dict[int, tuple[float, float]]
) -> float:
    """Where the line down to a wrapped row passes the rows over it.

    Immediately left of the COLUMN it is travelling past, not out at the edge
    of the block: a long run out, a long drop and a long run back draw a
    closed rectangle around a narrow row, and a box around four topics
    asserts a grouping the tree does not have (#197). Hugging the column
    leaves two short stubs and a bracket.
    """
    return min(kids[kid][0] for row in above for kid in row) - GUTTER / 2


def _path(points: Sequence[tuple[float, float]]) -> str:
    """An orthogonal run of segments, with its corners rounded off.

    Corners are rounded because a right-angled tree of ninety-degree joints
    reads as a circuit diagram; the radius shrinks on a short segment rather
    than overshooting it.
    """
    kept = [
        point
        for index, point in enumerate(points)
        if point not in points[:index]
    ]
    if len(kept) < 2:
        return ""
    out = [f"M{kept[0][0]},{kept[0][1]}"]
    for index in range(1, len(kept) - 1):
        before, corner, after = kept[index - 1], kept[index], kept[index + 1]
        turn = min(TURN, _apart(before, corner) / 2, _apart(corner, after) / 2)
        start, end = (
            _towards(corner, before, turn),
            _towards(corner, after, turn),
        )
        out.append(f"L{start[0]},{start[1]}")
        out.append(f"Q{corner[0]},{corner[1]} {end[0]},{end[1]}")
    out.append(f"L{kept[-1][0]},{kept[-1][1]}")
    return " ".join(out)


def _apart(one: tuple[float, float], other: tuple[float, float]) -> float:
    return abs(one[0] - other[0]) + abs(one[1] - other[1])


def _towards(
    corner: tuple[float, float], other: tuple[float, float], far: float
) -> tuple[float, float]:
    span = _apart(corner, other)
    if not span:
        return corner
    share = far / span
    return (
        round(corner[0] + (other[0] - corner[0]) * share, 1),
        round(corner[1] + (other[1] - corner[1]) * share, 1),
    )


def _radius(holds: int, biggest: int) -> float:
    """Area, not radius, follows what a topic holds.

    A circle is read by its area, so scaling the radius linearly makes a topic
    of thirty sections look nine times the one of ten rather than three.
    """
    share = (holds / biggest) ** 0.5 if biggest else 0.0
    return round(MIN_RADIUS + (MAX_RADIUS - MIN_RADIUS) * share, 1)


def _holds(row: sqlite3.Row) -> int:
    """What a topic contains: sections at the leaves, topics above them.

    One number for two kinds, because the question the size answers is "how
    much is under here", and an upper node's members are always zero (#163).
    """
    return int(row["members"]) or int(row["kids"])


def _holds_what(row: sqlite3.Row) -> str:
    """The unit `_holds` counted, so the page says it rather than implies it."""
    return "sections" if int(row["members"]) else "topics"


def _title(row: sqlite3.Row, node: int) -> str:
    if row["title"]:
        return _fitted(str(row["title"]), TITLE_CHARS)
    if row["brief"]:
        return _fitted(str(row["brief"]).strip().splitlines()[0], TITLE_CHARS)
    return f"topic {node}"


def _fitted_where(path: str) -> str:
    """Cut a path to its slot from the FRONT, keeping the telling end.

    ``src/hrono/server/templates`` cut at the tail reads as ``src/hrono/se…``,
    which is the half every topic shares. Dropping leading segments instead
    leaves ``…/server/templates``.
    """
    if len(path) <= LABEL_CHARS:
        return path
    parts = path.split("/")
    kept = parts[-1]
    for part in reversed(parts[:-1]):
        if len(part) + len(kept) + 3 > LABEL_CHARS:
            break
        kept = f"{part}/{kept}"
    return "…/" + _fitted(kept, LABEL_CHARS - 2)


def _fitted(text: str, budget: int) -> str:
    """Cut a label to its budget, with an ellipsis so the cut is visible."""
    if len(text) <= budget:
        return text
    return text[: budget - 1].rstrip(" ,;:.") + "…"
