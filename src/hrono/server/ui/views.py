"""The read-only views: config, activity, triage and the map.

Four pages that answer "what is in here" and "what needs attention", sharing
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
from hrono.server import config_view, graph, overlays, triage
from hrono.server.ui import Reader, _trees, router, templates

_LIVE = frozenset({"pending", "running", "partial"})

# Enough to recognise a chunk, not enough to lose the topic off the screen. A
# section is ~10 KB and a topic can hold thirty of them (#182).
PREVIEW_CHARS = 600


@router.get("/ui/config", response_class=HTMLResponse)
def config_page(request: Request, user: Reader, tree: str = "") -> Response:
    """Every registry collection, with secrets masked.

    Masked through the registry's OWN `mask()`, not a second redaction here: it
    reads each collection's declared `secret_paths` (#142), so a source type
    whose credential moves is masked by declaring the new path — and there is
    no second place that can forget to.
    """
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        collections = config_view.tables(conn)
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree if tree in trees else trees[0],
            "collections": collections,
            "can_write": user.role in {"writer", "admin"},
        },
    )


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
    return templates.TemplateResponse(
        request,
        "activity.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "rows": [_decision(row) for row in rows],
            "total": total,
            "can_write": user.role in {"writer", "admin"},
        },
    )


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
    open: str = "",
    edges: str = "",
    done: str = "",
) -> Response:
    """The tree, drawn — and every view of it is a URL.

    The expand state rides in `open` rather than in the page, so a graph
    someone is looking at can be pasted to someone else. It is also why this
    needs no JavaScript: toggling is a link.
    """
    opened = _opened(open)
    kinds = overlays.parse(edges)
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        drawn = graph.build(conn, tree, sorted(opened))
        overlay = overlays.build(
            conn, tree, [node.id for node in drawn.nodes], kinds
        )
        branches = _branches(conn, tree)
    return templates.TemplateResponse(
        request,
        "graph.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "graph": {
                "nodes": [
                    _with_toggle(node, tree, opened) for node in drawn.nodes
                ],
                "edges": drawn.edges,
                "width": drawn.width,
                "height": drawn.height,
                "shown": len(drawn.nodes),
                "expand_all": _graph_url(tree, _every(branches), edges),
                "collapse_all": _graph_url(tree, "", edges),
            },
            "overlay": {
                "links": _drawn_links(overlay, drawn),
                "unavailable": overlay.unavailable,
                "toggles": _edge_toggles(tree, open, kinds),
            },
            # a dissolve lands here rather than on the topic it just retired,
            # so this page is where its outcome has to be said
            "done": done,
            "can_write": user.role in {"writer", "admin"},
        },
    )


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


def _graph_url(tree: str, opened: str, edges: str) -> str:
    query = urlencode(
        {
            key: value
            for key, value in (
                ("tree", tree),
                ("open", opened),
                ("edges", edges),
            )
            if value
        },
        quote_via=quote,
        safe=",",
    )
    return f"/ui/trees/{tree}/graph?{query}"


def _drawn_links(
    overlay: overlays.Overlay, drawn: graph.Graph
) -> list[dict[str, object]]:
    """Give each link the coordinates of the topics it joins.

    A link whose end is not on the page is dropped rather than drawn to
    nowhere: the overlay describes what is DRAWN, and `?open=` decides that.
    """
    placed = {node.id: (node.x, node.y) for node in drawn.nodes}
    return [
        {
            "kind": link.kind,
            "label": link.label,
            "x1": placed[link.source][0],
            "y1": placed[link.source][1],
            "x2": placed[link.target][0],
            "y2": placed[link.target][1],
        }
        for link in overlay.links
        if link.source in placed and link.target in placed
    ]


def _edge_toggles(
    tree: str, open: str, kinds: Sequence[str]
) -> list[dict[str, object]]:
    """One on/off link per overlay, keeping the expand state.

    The overlay is part of the URL for the same reason the expand state is: a
    graph someone is looking at can be pasted to someone else.
    """
    toggles = []
    for kind in overlays.KINDS:
        rest = (
            [k for k in kinds if k != kind]
            if kind in kinds
            else [
                *kinds,
                kind,
            ]
        )
        query = urlencode(
            {
                k: v
                for k, v in (
                    ("tree", tree),
                    ("open", open),
                    ("edges", ",".join(rest)),
                )
                if v
            },
            quote_via=quote,
            safe=",",
        )
        toggles.append(
            {
                "kind": kind,
                "on": kind in kinds,
                "href": f"/ui/trees/{tree}/graph?{query}",
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
    node: object, tree: str, opened: set[int]
) -> dict[str, object]:
    """Each node carries the URL that opens or closes it."""
    node_id = node.id  # type: ignore[attr-defined]
    after = opened - {node_id} if node_id in opened else opened | {node_id}
    query = ",".join(str(value) for value in sorted(after))
    return {
        "id": node_id,
        "title": node.title,  # type: ignore[attr-defined]
        "holds": node.holds,  # type: ignore[attr-defined]
        "holds_what": node.holds_what,  # type: ignore[attr-defined]
        "level": node.level,  # type: ignore[attr-defined]
        "stale": node.stale,  # type: ignore[attr-defined]
        "has_children": node.has_children,  # type: ignore[attr-defined]
        "has_hidden_children": node.has_hidden_children,  # type: ignore[attr-defined]
        "x": node.x,  # type: ignore[attr-defined]
        "y": node.y,  # type: ignore[attr-defined]
        "radius": round(node.radius, 1),  # type: ignore[attr-defined]
        "toggle": f"/ui/trees/{tree}/graph?tree={tree}&open={query}",
    }
