"""Finding things: search, the outline and the file lookup.

Three pages, one question — where is it — so one module and one sub-navigation.
The reads are `server/find.py`'s; this only asks them and renders. All three
are GETs: asking changes nothing, and a result is a URL a person can send.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from hrono.server import find
from hrono.server.ui import Reader, _trees, router, templates

# Opened by default: the root only, so what is directly under it is the shape
# of the tree. Everything deeper is a click, or `open=all`.
OPEN_LEVELS = 1


@router.get("/ui/trees/{tree}/find", response_class=HTMLResponse)
def find_page(
    request: Request, user: Reader, tree: str, q: str = ""
) -> Response:
    """Words, in topic names, briefs, section paths and section text."""
    query = q.strip()
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        found = find.search(conn, tree, query) if query else None
    return templates.TemplateResponse(
        request,
        "find.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "page": "search",
            "query": query,
            "found": found,
        },
    )


@router.get("/ui/trees/{tree}/outline", response_class=HTMLResponse)
def outline_page(
    request: Request, user: Reader, tree: str, open: str = ""
) -> Response:
    """The whole tree as a collapsible list."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        rows = find.outline(conn, tree)
    return templates.TemplateResponse(
        request,
        "outline.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "page": "outline",
            "rows": rows,
            "expanded": open == "all",
            "open_levels": OPEN_LEVELS,
            "topics": sum(_count(row) for row in rows),
        },
    )


@router.get("/ui/trees/{tree}/files", response_class=HTMLResponse)
def files_page(
    request: Request, user: Reader, tree: str, path: str = ""
) -> Response:
    """A file path, or a directory, to its sections and their topics."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        located = find.lookup(conn, tree, path) if path.strip() else None
    return templates.TemplateResponse(
        request,
        "files.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "page": "files",
            "path": path.strip(),
            "located": located,
        },
    )


def _count(row: find.Row) -> int:
    return 1 + sum(_count(kid) for kid in row.kids)
