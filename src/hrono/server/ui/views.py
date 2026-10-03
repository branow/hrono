"""The read-only views: activity, triage and the map.

Three pages that answer "what is in here" and "what needs attention", sharing
one shape — read under one connection, render, write nothing. The map's expand
state and edge overlays ride in the URL rather than in the page, which is what
makes every view of it shareable (#183, #184).
"""

from __future__ import annotations

from collections.abc import Sequence
from urllib.parse import quote, urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from hrono.db import update_log
from hrono.server import graph, overlays, panel, triage
from hrono.server.ui import Reader, _trees, router, templates

_LIVE = frozenset({"pending", "running", "partial"})

# The overlays the MAP offers. `propagation` is deliberately not among them
# (#200): it is a record of judge decisions a sync already made, which is a
# thing you REVIEW, not a repair you perform on the board — and it draws
# nothing at all on a tree that has never been re-synced, which is how most
# people met it. It lives on the Activity page, beside the decisions it is
# made of. The URL still accepts it; only the toggle is gone.
MAP_EDGES = ("pull", "proximity")

# A first visit should show a useful amount of tree rather than one circle
# nobody knows to click. Two: the root and what is directly under it, which
# is the shape of the tree rather than the whole of it.
OPEN_DEPTH = 2
# The sentinel for "no `open` parameter at all", distinct from one that is
# present and empty — which is exactly what the Collapse link sends.
NO_OPEN = "\x00"


def _down_to(conn: object, tree: str, depth: int) -> set[int]:
    """Every topic shallow enough that opening it is still worth the room.

    A DEPTH from the top rather than a list of ids, so it means the same thing
    on a tree of three levels and one of nine.
    """
    rows = conn.execute(  # type: ignore[attr-defined]
        "SELECT id, level FROM nodes WHERE tree = ?", (tree,)
    ).fetchall()
    if not rows:
        return set()
    top = max(int(row["level"]) for row in rows)
    return {
        int(row["id"]) for row in rows if top - int(row["level"]) < depth - 1
    }


# Enough to recognise a section, not enough to lose the topic off the screen. A
# section is ~10 KB and a topic can hold thirty of them (#182).
PREVIEW_CHARS = 600


@router.get("/ui/trees/{tree}/activity", response_class=HTMLResponse)
def activity_page(tree: str, request: Request, user: Reader) -> Response:
    """What the tree DECIDED — the only record of its own judgement.

    A stale brief is a fact; "judged, not materially changed, did not climb" is
    a decision, and an operator who disagrees with the map needs to read the
    decision rather than infer it from the shape.
    """
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        rows, total = update_log.recent(conn, tree)
    decided = [_decision(row) for row in rows]
    return templates.TemplateResponse(
        request,
        "activity.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "rows": decided,
            "total": total,
            "climbs": _climbs(decided),
            "can_write": user.role in {"writer", "admin"},
        },
    )


# How tall the climb figure is, and how far apart its levels sit.
CLIMB_STEP = 44
CLIMB_PAD = 22


def _climbs(decided: list[dict[str, object]]) -> dict[str, object]:
    """The climbs in this log, drawn — what a list of rows cannot show.

    Each row says "topic 12 climbed to topic 18". Twelve such rows do not say
    the thing an operator actually wants to know, which is SHAPE: whether one
    commit restaled a corner of the map or swept it to the root. This used to
    be a map overlay (#200); it belongs here, over the decisions it is made
    of, and on a tree with no decisions there is simply nothing to draw.
    """
    climbed = [
        (int(row["node_id"]), int(row["climbed_to"]))  # type: ignore[arg-type]
        for row in decided
        if row["climbed_to"] and int(row["climbed_to"]) != int(row["node_id"])  # type: ignore[arg-type]
    ]
    if not climbed:
        return {"links": [], "width": 0, "height": 0}
    tops = sorted({top for _, top in climbed})
    leaves = sorted({leaf for leaf, _ in climbed})
    place = {node: index for index, node in enumerate(leaves)}
    high = {node: index for index, node in enumerate(tops)}
    width = max(len(leaves), len(tops)) * 120 + CLIMB_PAD * 2
    return {
        "width": width,
        "height": CLIMB_STEP * 2 + CLIMB_PAD * 2,
        "links": [
            {
                "from": leaf,
                "to": top,
                "x1": CLIMB_PAD + place[leaf] * 120 + 60,
                "y1": CLIMB_PAD + CLIMB_STEP,
                "x2": CLIMB_PAD + high[top] * 120 + 60,
                "y2": CLIMB_PAD,
            }
            for leaf, top in sorted(set(climbed))
        ],
    }


def _decision(row: object) -> dict[str, object]:
    """One logged decision, with the abstention called out.

    #105 made abstaining a first-class outcome and #132 made it visible in a
    job's result, because a topic that CHANGED and was not judged leaves a
    stale brief in service. On this page that is the row to look at.
    """
    action = str(row["action"])  # type: ignore[index]
    return {
        "node_id": int(row["node_id"]),  # type: ignore[index]
        "verdict": str(row["verdict"]),  # type: ignore[index]
        "action": action,
        "climbed_to": row["climbed_to"],  # type: ignore[index]
        "when": str(row["created_at"])[:19].replace("T", " "),  # type: ignore[index]
        # the ACTION carries it, not the verdict: `_record` writes the verdict
        # as "unparseable" and the action as "abstained" (propagate.py)
        "abstained": action == "abstained",
    }


@router.get("/ui/trees/{tree}/triage", response_class=HTMLResponse)
def triage_page(tree: str, request: Request, user: Reader) -> Response:
    """What is wrong with this tree, counted, each linking to where it is."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        items = triage.survey(conn, tree)
    return templates.TemplateResponse(
        request,
        "triage.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "items": items,
            "clean": triage.clean(items),
            "can_write": user.role in {"writer", "admin"},
        },
    )


@router.get("/ui/trees/{tree}/graph", response_class=HTMLResponse)
def graph_page(
    tree: str,
    request: Request,
    user: Reader,
    open: str = NO_OPEN,
    edges: str = "",
    done: str = "",
    focus: str = "",
) -> Response:
    """The tree, drawn — and every view of it is a URL.

    The expand state rides in `open` rather than in the page, so a graph
    someone is looking at can be pasted to someone else. It is also why this
    needs no JavaScript: toggling is a link, and so is reading a topic —
    `focus` opens the panel beside the map on the server (#199).
    """
    # `?open=` present means the view was chosen — even when empty, which is
    # what Collapse posts. Absent means a first visit, which opens enough
    # tree to be worth looking at.
    chosen = _opened(open) if open is not None and open != NO_OPEN else None
    kinds = overlays.parse(edges)
    wanted = int(focus) if focus.strip().isdigit() else 0
    with request.app.state.db.connect() as conn:
        opened = (
            chosen if chosen is not None else _down_to(conn, tree, OPEN_DEPTH)
        )
        trees = _trees(conn)
        drawn = graph.build(conn, tree, sorted(opened))
        overlay = overlays.build(
            conn, tree, [node.id for node in drawn.nodes], kinds
        )
        branches = _branches(conn, tree)
        focused = panel.build(conn, tree, wanted) if wanted else None
    links = _drawn_links(overlay, drawn)
    return templates.TemplateResponse(
        request,
        "graph.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "graph": {
                "nodes": [
                    _with_toggle(node, tree, opened, open, edges, wanted)
                    for node in drawn.nodes
                ],
                "edges": drawn.edges,
                "width": drawn.width,
                "height": _tall_enough(drawn.height, links),
                "home": _home(drawn, wanted),
                "shown": len(drawn.nodes),
                # ONE control, not two: a map is either all open or it is
                # not, and two mutually exclusive buttons sitting side by side
                # made the reader work out which one was already true (#200)
                "fold": _folding(tree, opened, branches, edges, focus),
            },
            "overlay": {
                "links": links,
                "unavailable": overlay.unavailable,
                "toggles": _edge_toggles(tree, open, kinds, focus),
            },
            "panel": focused,
            # a child in the panel is a link back onto the map, and it has to
            # be the map the reader is ON — the hard-coded one in the template
            # dropped the expand state and the overlays, so clicking a child
            # collapsed the board under the reader (#200)
            "reads": {
                part.id: _graph_url(tree, open, edges, focus=str(part.id))
                for part in (focused.parts if focused else ())
            },
            # closing the panel is the same map without it, which keeps the
            # expand state and the overlays the reader had set up
            "unfocus": _graph_url(tree, open, edges),
            # a dissolve lands here rather than on the topic it just retired,
            # so this page is where its outcome has to be said
            "done": done,
            "can_write": user.role in {"writer", "admin"},
        },
    )


# Room under the lowest thing an overlay draws, so its label is not against
# the edge of the canvas.
MARGIN = 28.0


def _tall_enough(height: float, links: list[dict[str, object]]) -> float:
    """The canvas, grown to fit whatever the overlays put on it.

    An overlay arc leaves the row it joins (`_drawn`), and the SVG is sized
    from the TREE — so with the arcs added the drawing was taller than the box
    it was drawn in, and every arc and every label was cut off at the bottom
    edge (#200). The board is a scrolling box; it can simply be taller.
    """
    lowest = max((float(link["y"]) for link in links), default=0.0)
    return max(height, lowest + MARGIN)


def _home(drawn: graph.Graph, focused: int) -> float:
    """Where the board should be looking when the page arrives.

    The canvas is as wide as the tree, so its left edge is an arbitrary place
    to land. The root is the non-arbitrary one — except when a topic is being
    read, where the one the reader just clicked is.
    """
    for node in drawn.nodes:
        if node.id == focused:
            return node.x
    return drawn.home


def _branches(conn: object, tree: str) -> set[int]:
    """Every topic in the tree that has something beneath it.

    Opening a LEAF is a no-op, so "open everything" only needs these — which
    keeps the URL short on a tree whose leaves outnumber its branches many
    times over.
    """
    return {
        int(row["parent_id"])
        for row in conn.execute(  # type: ignore[attr-defined]
            "SELECT DISTINCT c.parent_id AS parent_id FROM node_children c "
            "JOIN nodes n ON n.id = c.parent_id WHERE n.tree = ?",
            (tree,),
        ).fetchall()
    }


def _every(branches: set[int]) -> str:
    return ",".join(str(node) for node in sorted(branches))


def _folding(
    tree: str,
    opened: set[int],
    branches: set[int],
    edges: str,
    focus: str,
) -> dict[str, str]:
    """The one fold control: what it would do, and where it goes.

    Expand-all and collapse-all are not two choices, they are one state read
    two ways. Drawn as two buttons, the reader has to work out which of them
    is already true before either is safe to press.
    """
    wide_open = branches <= opened
    return {
        "label": "Collapse" if wide_open else "Expand all",
        "says": (
            "Show only the root"
            if wide_open
            else "Open every topic that has something under it"
        ),
        "href": _graph_url(
            tree,
            "" if wide_open else _every(branches),
            edges,
            focus=focus,
        ),
    }


def _graph_url(tree: str, opened: str, edges: str, focus: str = "") -> str:
    """A link to one view of the map.

    `open` is emitted even when EMPTY, and that is the whole of the Collapse
    link: an absent `open` means a first visit, which opens several levels, so
    dropping an empty one turned Collapse into Expand (#197). The one `open`
    that must NOT be emitted is the sentinel for "there wasn't one" — passing
    it through put a literal `open=%00` in the links of every first visit.
    Every other parameter is omitted when it has nothing to say.
    """
    query = urlencode(
        {
            key: value
            for key, value in (
                ("tree", tree),
                ("open", "" if opened == NO_OPEN else opened),
                ("edges", edges),
                ("focus", focus),
            )
            if value or (key == "open" and opened != NO_OPEN)
        },
        quote_via=quote,
        safe=",",
    )
    return f"/ui/trees/{tree}/graph?{query}"


def _drawn_links(
    overlay: overlays.Overlay, drawn: graph.Graph
) -> list[dict[str, object]]:
    """Give each link the path that joins the topics it is about, and a place
    to say what it found.

    A link whose end is not on the page is dropped rather than drawn to
    nowhere: the overlay describes what is DRAWN, and `?open=` decides that.
    """
    placed = {node.id: (node.x, node.y) for node in drawn.nodes}
    here = [
        (link, placed[link.source], placed[link.target])
        for link in overlay.links
        if link.source in placed and link.target in placed
    ]
    lanes = _lanes(here)
    return [
        _drawn(link, start, end, lanes.get(id(link), 0))
        for link, start, end in here
    ]


# How a same-row link bows away from the row. The floor is what matters: the
# arc has to clear BOTH lines of text under a topic (the name and the counts,
# ~45px down), or the overlay's own label lands on top of them. Links that
# overlap each other step down a lane at a time so no two labels share a spot.
BOW_FLOOR = 130.0
LANE = 54.0
BOW_CAP = 420.0


def _lanes(
    drawn: list[tuple[overlays.Link, tuple[float, float], tuple[float, float]]],
) -> dict[int, int]:
    """How deep each same-row arc goes, so overlapping ones do not coincide.

    Three arcs over adjacent siblings all span the same distance, so at one
    depth their apexes — and the labels sitting on them — land on top of each
    other and read as one run-on string (#200). Greedy interval colouring: an
    arc takes the shallowest lane no arc it OVERLAPS is already using.
    """
    spans = sorted(
        (
            (min(start[0], end[0]), max(start[0], end[0]), id(link))
            for link, start, end in drawn
            if abs(start[1] - end[1]) <= 1
        ),
        key=lambda span: (span[0], span[1]),
    )
    taken: list[float] = []  # the right edge held by each lane so far
    lanes: dict[int, int] = {}
    for left, right, key in spans:
        lane = next(
            (index for index, edge in enumerate(taken) if edge <= left),
            len(taken),
        )
        if lane == len(taken):
            taken.append(right)
        else:
            taken[lane] = right
        lanes[key] = lane
    return lanes


def _drawn(
    link: overlays.Link,
    start: tuple[float, float],
    end: tuple[float, float],
    lane: int,
) -> dict[str, object]:
    """One overlay link: its path, and where its label sits ON that path.

    Siblings sit on one row, so a straight line between two of them runs
    THROUGH every topic in between: a reader sees a horizontal rule crossing
    five circles and cannot tell which two it is about (#200). An arc leaves
    the row, so both ends are visible and the pair is unambiguous — and the
    label goes at the arc's own apex rather than at a fixed offset, which is
    what kept putting it over a topic's section count.
    """
    (x1, y1), (x2, y2) = start, end
    middle = (x1 + x2) / 2
    if abs(y1 - y2) > 1:
        # already travels between levels: a straight line crosses nothing
        return _link(link, f"M{x1},{y1} L{x2},{y2}", middle, (y1 + y2) / 2)
    bow = min(BOW_FLOOR + lane * LANE, BOW_CAP)
    return _link(
        link,
        f"M{x1},{y1} Q{middle},{y1 + bow} {x2},{y2}",
        middle,
        # the apex of a quadratic sits HALF way to its control point
        y1 + bow / 2,
    )


def _link(
    link: overlays.Link, path: str, x: float, y: float
) -> dict[str, object]:
    return {
        "kind": link.kind,
        "label": link.label,
        "d": path,
        "x": round(x, 1),
        "y": round(y, 1),
    }


def _edge_toggles(
    tree: str, open: str, kinds: Sequence[str], focus: str = ""
) -> list[dict[str, object]]:
    """One on/off link per overlay, keeping the expand state.

    The overlay is part of the URL for the same reason the expand state is: a
    graph someone is looking at can be pasted to someone else — which is why
    this builds its link through `_graph_url` like every other link on the
    page rather than assembling a second one of its own. The copy it used to
    keep dropped an EMPTY `open`, so turning an overlay on from a collapsed
    map re-opened the map (the #197 bug, in the one place that was not fixed).
    """
    toggles = []
    for kind in MAP_EDGES:
        rest = (
            [k for k in kinds if k != kind]
            if kind in kinds
            else [
                *kinds,
                kind,
            ]
        )
        toggles.append(
            {
                "kind": kind,
                "on": kind in kinds,
                "href": _graph_url(tree, open, ",".join(rest), focus=focus),
            }
        )
    return toggles


def _opened(raw: str) -> set[int]:
    """The ids in `?open=`, ignoring anything that is not one.

    A hand-edited or truncated URL should draw a smaller graph, never a 500 —
    this parameter is a view, and a view cannot be invalid.
    """
    out: set[int] = set()
    for part in raw.split(","):
        if part.strip().isdigit():
            out.add(int(part))
    return out


def _with_toggle(
    node: object,
    tree: str,
    opened: set[int],
    open: str,
    edges: str,
    focused: int,
) -> dict[str, object]:
    """Each node carries the URL that opens it, and the one that reads it.

    Reading a topic is `?focus=` on the map rather than a link to the topic
    page: the question a click asks is about a topic IN its tree, and
    answering it somewhere the tree is not visible throws the question away
    (#199). The topic page is one link further on, in the panel.
    """
    node_id = node.id  # type: ignore[attr-defined]
    after = opened - {node_id} if node_id in opened else opened | {node_id}
    query = ",".join(str(value) for value in sorted(after))
    focus = "" if node_id == focused else str(node_id)
    return {
        "id": node_id,
        "where": node.where,  # type: ignore[attr-defined]
        "label": node.label,  # type: ignore[attr-defined]
        "spread": node.spread,  # type: ignore[attr-defined]
        "title": node.title,  # type: ignore[attr-defined]
        "holds": node.holds,  # type: ignore[attr-defined]
        "holds_what": node.holds_what,  # type: ignore[attr-defined]
        "level": node.level,  # type: ignore[attr-defined]
        "stale": node.stale,  # type: ignore[attr-defined]
        "has_children": node.has_children,  # type: ignore[attr-defined]
        "has_hidden_children": node.has_hidden_children,  # type: ignore[attr-defined]
        "focused": node_id == focused,
        "x": node.x,  # type: ignore[attr-defined]
        "y": node.y,  # type: ignore[attr-defined]
        "radius": round(node.radius, 1),  # type: ignore[attr-defined]
        # through `_graph_url` so a chevron keeps the overlays too: its own
        # hand-built URL dropped `edges`, and opening a topic turned off the
        # overlay the reader had opened it to look at
        "toggle": _graph_url(
            tree, query, edges, focus=str(focused) if focused else ""
        ),
        # clicking the focused topic again closes its panel, so the disc is a
        # toggle like everything else on this page
        "read": _graph_url(tree, open, edges, focus=focus),
    }
