"""Laying a tree out for the page.

Arithmetic, not a library. A hierarchy drawn level by level is positions and
line segments, and SVG is markup — so the graph is rendered by the same Jinja
that renders everything else, with no JS dependency to vendor, review and pin.

The layout is a TOP-DOWN TREE of BLOCKS: the root sits at the top and its
children hang below it, SIDE BY SIDE, however many there are. It is not a
left-to-right dendrogram — the shape a file explorer has, which nobody reads
as a tree — and it does not WRAP a wide family onto further rows to keep the
whole map inside one window. Wrapping buys that width by putting a topic's
right-hand subtree underneath its left-hand one, and two subtrees stacked read
as one over the other rather than as siblings. So
siblings stay on one level and the canvas gets as wide as the tree needs; the
page makes it a board the reader moves around instead.

Each topic is labelled by its NAME (`hrono.naming`, the rule the export and
every other page use), with where its sections live (`server/where.py`) on the
line beneath. Where-it-lives is not the label, because siblings often share
it: a tree can have four siblings called ``src/click``. A title two siblings
share carries the topic's number, so no two read alike.

The expand state is a QUERY PARAMETER rather than client state, which is what
makes every view of the graph a URL: bookmarkable, shareable, and testable as
HTML rather than as a screenshot.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from hrono import naming
from hrono.server import where as where_module
from hrono.summarize import briefs

# A topic's own footprint: one cell wide, with its circle at the top and its
# two lines of text centred under it.
SLOT = 130
# Vertical room a topic's own furniture needs below the top of its cell: the
# circle, its name, where it lives, its count. A topic that can be opened
# carries a chevron under those.
NODE_HEIGHT = 86
CHEVRON = 18
# Between a parent's furniture and its children.
DROP = 30
# Half a label either side of the drawing, so no name is cut by the canvas.
PAD = 20
TOP = 10
BOTTOM = 8
# A label must fit inside its slot or it collides with its neighbour's and is
# cut by the canvas edge. The label font is 11.5px mono, ~6.9px a character,
# so 16 of them fit a 130px slot with a gutter to spare.
LABEL_CHARS = 16
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
    depth: int  # steps below the drawn root it hangs from, for the list
    name: str  # what it is called: `hrono.naming`, the same everywhere
    label: str  # `name`, cut to fit its slot
    where: str  # the directory its sections live in
    place: str  # `where`, cut to fit its slot
    spread: str  # the shares behind a label that had to name two places
    title: str  # what its brief calls it, for the tooltip and the topic page
    holds: int  # members for a leaf, children for an upper topic
    holds_what: str  # "sections" or "topics" — the unit `holds` counts
    stale: bool
    branch: int  # which top-level subtree it belongs to, for its tint
    has_children: bool
    has_hidden_children: bool
    x: float
    y: float
    radius: float


@dataclass(frozen=True)
class Graph:
    """A drawn tree: placed nodes, connector paths, and the canvas they need.

    ``edges`` is SVG path data rather than endpoints because a connector is a
    run of right angles, not a segment: out of the parent, along the rail its
    children sit on, and down into each of them.

    ``home`` is where the reader should be looking when the page opens. The
    canvas is as wide as the tree, so its left edge is an arbitrary place
    to start and the root is the only non-arbitrary one.
    """

    nodes: tuple[Node, ...]
    edges: tuple[str, ...]
    width: float
    height: float
    home: float


@dataclass(frozen=True)
class _Box:
    """What one topic and everything drawn beneath it occupies."""

    width: float
    height: float


def build(conn: sqlite3.Connection, tree: str, opened: Sequence[int]) -> Graph:
    """Draw the root, and the children of every OPEN topic below it."""
    rows = _rows(conn, tree)
    if not rows:
        return Graph(nodes=(), edges=(), width=0, height=0, home=0)
    children = _children(conn, tree)
    roots = _roots(rows, children)
    visible = _visible(roots, children, set(opened))
    return _lay_out(
        conn,
        rows,
        children,
        visible,
        set(opened),
        where_module.describe(conn, tree),
        naming.names(conn, visible),
    )


def _rows(conn: sqlite3.Connection, tree: str) -> dict[int, sqlite3.Row]:
    return {
        int(row["id"]): row
        for row in conn.execute(
            "SELECT n.id AS id, n.level AS level, n.title AS title, "
            "b.text AS brief, COALESCE(b.stale, 0) AS stale, "
            f"b.flagged AS flagged, {briefs.TEMPLATE} AS template, "
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
    hide exactly the state an operator opened the graph to find.
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


# How many tints the sheet defines. A subtree past the last one wraps round
# rather than going uncoloured — a repeated tint is a smaller lie than an
# unmarked branch, because the tints say "these are siblings", never "this is
# branch four".
TINTS = 6


def _branches(
    roots: Sequence[int], children: dict[int, list[int]]
) -> dict[int, int]:
    """Which top-level subtree each drawn topic sits in.

    Taken from the root's CHILDREN rather than from the roots themselves: with
    one root every topic would share a tint and the whole thing would be
    pointless, and the division a reader cares about is the first fork, not the
    trunk. The root itself is 0 — it belongs to all of them.
    """
    tops = [kid for root in roots for kid in children.get(root, ())] or list(
        roots
    )
    out: dict[int, int] = {root: 0 for root in roots}
    for index, top in enumerate(tops):
        stack = [top]
        while stack:
            node = stack.pop()
            out.setdefault(node, index % TINTS + 1)
            stack.extend(children.get(node, ()))
    return out


def _lay_out(
    conn: sqlite3.Connection,
    rows: dict[int, sqlite3.Row],
    children: dict[int, list[int]],
    visible: Sequence[int],
    opened: set[int],
    wheres: dict[int, where_module.Where],
    called: dict[int, str],
) -> Graph:
    """A block per topic: its own cell, then its children in ONE row beneath.

    A wide family makes a wide canvas, which is the trade made here: a reader
    can pan a wide tree, and cannot read a subtree that was folded underneath
    its sibling.
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
    shown_as = _labels(
        visible,
        drawn_kids,
        called,
        {node: boxes[node].width for node in visible},
    )
    tops = _drawn_roots(visible, drawn_kids)
    placed, edges, width, height = _place(tops, boxes, drawn_kids, radii, tall)
    blank = where_module.Where("", "")
    tint = _branches(tops, drawn_kids)
    depth = _depths(tops, drawn_kids)
    drawn = tuple(
        Node(
            id=node,
            level=int(rows[node]["level"]),
            depth=depth[node],
            name=called.get(node, f"topic {node}"),
            label=shown_as[node],
            where=wheres.get(node, blank).label,
            place=_fitted_where(wheres.get(node, blank).label),
            spread=wheres.get(node, blank).spread,
            title=_title(rows[node], node),
            holds=holds[node],
            holds_what=_holds_what(rows[node]),
            stale=bool(rows[node]["stale"])
            or rows[node]["brief"] is None
            or bool(
                briefs.refusal(
                    conn,
                    node,
                    rows[node]["flagged"],
                    rows[node]["brief"],
                    rows[node]["template"],
                )
            ),
            branch=tint.get(node, 0),
            has_children=bool(children.get(node)),
            has_hidden_children=bool(children.get(node)) and node not in opened,
            x=placed[node][0],
            y=placed[node][1],
            radius=radii[node],
        )
        for node in visible
    )
    return Graph(
        nodes=drawn,
        edges=edges,
        width=width,
        height=height,
        home=_home(tops, placed),
    )


def _depths(
    tops: Sequence[int], drawn_kids: dict[int, list[int]]
) -> dict[int, int]:
    """How far below its drawn root each topic hangs.

    Counted down the DRAWN tree, not read from ``level``: a level counts from
    the leaves, so two siblings of different heights carry different levels,
    and indenting by it would put them at different depths in the list.
    """
    out: dict[int, int] = {}
    stack = [(top, 0) for top in tops]
    while stack:
        node, steps = stack.pop()
        out[node] = steps
        stack.extend((kid, steps + 1) for kid in drawn_kids[node])
    return out


def _home(tops: Sequence[int], placed: dict[int, tuple[float, float]]) -> float:
    """The x the canvas opens on: the middle of the topmost row.

    With one root that is the root itself. With several — a tree mid-repair —
    it is the middle of them, because arriving centred on whichever happens to
    be first would hide that there are others.
    """
    if not tops:
        return 0
    across = [placed[node][0] for node in tops]
    return (min(across) + max(across)) / 2


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
            boxes[node] = _Box(SLOT, tall[node])
            continue
        boxes[node] = _Box(
            width=max(SLOT, _spanned(kids, boxes)),
            height=tall[node] + DROP + max(boxes[kid].height for kid in kids),
        )
    return boxes


def _spanned(nodes: Sequence[int], boxes: dict[int, _Box]) -> float:
    return sum(boxes[node].width for node in nodes)


def _place(
    roots: Sequence[int],
    boxes: dict[int, _Box],
    drawn_kids: dict[int, list[int]],
    radii: dict[int, float],
    tall: dict[int, float],
) -> tuple[dict[int, tuple[float, float]], tuple[str, ...], float, float]:
    """Walk the blocks top-down, placing each and drawing what joins them."""
    spread = _spanned(roots, boxes)
    placed: dict[int, tuple[float, float]] = {}
    edges: list[str] = []
    stack = _laid(roots, boxes, PAD, spread, TOP)
    while stack:
        node, left, top = stack.pop()
        box = boxes[node]
        placed[node] = (left + box.width / 2, top + MAX_RADIUS)
        kids = drawn_kids[node]
        if not kids:
            continue
        foot = top + tall[node]
        laid = _laid(kids, boxes, left, box.width, foot + DROP)
        edges.extend(_connectors(placed[node], foot, laid, boxes, radii))
        stack.extend(laid)
    return (
        placed,
        tuple(edges),
        spread + PAD * 2,
        TOP + max(boxes[node].height for node in roots) + BOTTOM,
    )


def _laid(
    nodes: Sequence[int],
    boxes: dict[int, _Box],
    left: float,
    width: float,
    top: float,
) -> list[tuple[int, float, float]]:
    """Give every topic in a family its own corner, all on the same level.

    The row is CENTRED in the space its parent occupies, so a parent sits over
    the middle of what it owns whichever way the widths fall.
    """
    out: list[tuple[int, float, float]] = []
    x = left + (width - _spanned(nodes, boxes)) / 2
    for node in nodes:
        out.append((node, x, top))
        x += boxes[node].width
    return out


def _connectors(
    parent: tuple[float, float],
    foot: float,
    kids: Sequence[tuple[int, float, float]],
    boxes: dict[int, _Box],
    radii: dict[int, float],
) -> list[str]:
    """One path per child, so a connector is never a line to nowhere.

    Down from the parent to a rail half a drop below it, along the rail, and
    down into each child — the shape a family tree has.
    """
    rail = foot + DROP / 2
    out: list[str] = []
    for node, left, top in kids:
        x = left + boxes[node].width / 2
        out.append(
            _path(
                [
                    (parent[0], foot),
                    (parent[0], rail),
                    (x, rail),
                    (x, top + MAX_RADIUS - radii[node]),
                ]
            )
        )
    return out


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
    much is under here", and an upper node's members are always zero.
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


def _labels(
    visible: Sequence[int],
    drawn_kids: dict[int, list[int]],
    called: dict[int, str],
    room: dict[int, float],
) -> dict[int, str]:
    """Each topic's label, still told apart from its siblings once CUT.

    A name is cut to the room its column has, and where siblings open with the
    same words the shared words are what is dropped, not the end: three
    "Handles assorted material for ..." cut at the slot all read "Handles
    assorted mat...". Two names can still differ only past the cut; they would
    read the same, so a cut that collides takes the topic's number as well.
    """
    hung = {kid for kids in drawn_kids.values() for kid in kids}
    families = [kids for kids in drawn_kids.values() if kids]
    families.append([node for node in visible if node not in hung])
    labels: dict[int, str] = {}
    for family in families:
        names = {node: called.get(node, f"topic {node}") for node in family}
        cut = {
            node: _cut_among(
                names[node], list(names.values()), _budget(room[node])
            )
            for node in family
        }
        seen: dict[str, int] = {}
        for label in cut.values():
            seen[label] = seen.get(label, 0) + 1
        for node in family:
            name = names[node]
            clash = seen[cut[node]] > 1 and " (#" not in name
            labels[node] = (
                _cut(f"{name} (#{node})", _budget(room[node]))
                if clash
                else cut[node]
            )
    return labels


def _budget(room: float) -> int:
    """How many characters of a name fit in ``room`` pixels, never fewer than a
    slot's worth and never more than a title."""
    return min(TITLE_CHARS, max(LABEL_CHARS, int(room // LABEL_CHAR) - 2))


def _cut_among(name: str, siblings: Sequence[str], budget: int) -> str:
    """``name`` cut to ``budget``, with the words it shares with a sibling
    dropped from the front when there is something past them to show."""
    if len(name) <= budget:
        return name
    shared = max(
        (_shared_words(name, other) for other in siblings if other != name),
        key=len,
        default="",
    )
    rest = name[len(shared) :].strip()
    if not shared or not rest:
        return _cut(name, budget)
    return "…" + _cut(rest, budget - 1)


def _shared_words(name: str, other: str) -> str:
    """The leading whole words two names have in common, with their spacing."""
    kept: list[str] = []
    for ours, theirs in zip(name.split(" "), other.split(" "), strict=False):
        if ours != theirs:
            break
        kept.append(ours)
    return " ".join(kept) + " " if kept else ""


def fitted_name(name: str) -> str:
    """Cut a name to its slot, never cutting off what tells it apart."""
    return _cut(name, LABEL_CHARS)


def _cut(name: str, budget: int) -> str:
    """Cut a name to ``budget``, keeping the topic's number if it has one.

    ``naming`` ends a shared title with the topic's number; a cut that took
    the number with it would put two identical labels back side by side.
    """
    if len(name) <= budget:
        return name
    title, mark, number = name.rpartition(" (#")
    if not mark:
        return _fitted(name, budget)
    tail = f" (#{number}"
    return _fitted(title, budget - len(tail)) + tail


def _fitted_where(place: str) -> str:
    """Cut a place to its slot, keeping the telling end of each path in it.

    A straddling topic is named by TWO paths (`server/where.py`), and cutting
    that as one string drops the whole of the second. Neither side fits with
    its parent directories either, so each is reduced to the directory it
    actually names: ``src/hrono/db + tests/cluster`` reads ``db + cluster``,
    and the pair in full, with its shares, is on the tooltip and the panel.
    """
    if len(place) <= LABEL_CHARS:
        return place
    if where_module.STRADDLE in place:
        share = (LABEL_CHARS - len(where_module.STRADDLE)) // 2
        return where_module.STRADDLE.join(
            _fitted(part.rsplit("/", 1)[-1], share)
            for part in place.split(where_module.STRADDLE, 1)
        )
    return _tail(place, LABEL_CHARS)


def _tail(path: str, budget: int) -> str:
    """Cut a path to its budget from the FRONT, keeping the telling end.

    ``src/hrono/server/templates`` cut at the tail reads as ``src/hrono/se…``,
    which is the half every topic shares. Dropping leading segments instead
    leaves ``…/server/templates``.
    """
    if len(path) <= budget:
        return path
    if "/" not in path:
        return _fitted(path, budget)
    parts = path.split("/")
    kept = parts[-1]
    for part in reversed(parts[:-1]):
        if len(part) + len(kept) + 3 > budget:
            break
        kept = f"{part}/{kept}"
    return "…/" + _fitted(kept, budget - 2)


def _fitted(text: str, budget: int) -> str:
    """Cut a label to its budget, with an ellipsis so the cut is visible."""
    if len(text) <= budget:
        return text
    return text[: budget - 1].rstrip(" ,;:.") + "…"


def opened_to(conn: sqlite3.Connection, tree: str, seen: list[int]) -> set[int]:
    """``seen`` and every topic above them, the root at least: the ``opened``
    a view needs so that each of them is drawn."""
    parent = {
        int(row["child"]): int(row["parent"])
        for row in conn.execute(
            "SELECT c.parent_id AS parent, c.child_id AS child "
            "FROM node_children c JOIN nodes n ON n.id = c.parent_id "
            "WHERE n.tree = ?",
            (tree,),
        ).fetchall()
    }
    root = conn.execute(
        "SELECT id FROM nodes WHERE tree = ? ORDER BY level DESC, id LIMIT 1",
        (tree,),
    ).fetchone()
    opened = {int(root["id"])} if root else set()
    for node in seen:
        while node not in opened:
            opened.add(node)
            if node not in parent:
                break
            node = parent[node]
    return opened
