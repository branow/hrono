"""Finding things: search, the outline and the file lookup.

Two pages, one question — where is it — so one module and one sub-navigation.
Search also answers "where did this file go", narrowed to files.
The reads are `server/find.py`'s; this only asks them and renders. Both are
GETs: asking changes nothing, and a result is a URL a person can send.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from hrono.server import find
from hrono.server.ui import Reader, _trees, router, templates

# Opened by default: the root only, so what is directly under it is the shape
# of the tree. Everything deeper is a click, or `open=all`.
OPEN_LEVELS = 1


SCOPES = ("all", "topics", "files")


@router.get("/ui/trees/{tree}/find", response_class=HTMLResponse)
def find_page(
    request: Request, user: Reader, tree: str, q: str = "", within: str = "all"
) -> Response:
    """Words, in topic names, briefs, section paths and section text.

    ``within`` narrows to topics or to files. With files, a query that reads
    as a path also lists every section cut from the files under it, which is
    the question "where did this file go" the Files page used to answer.
    """
    query = q.strip()
    scope = within if within in SCOPES else "all"
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        found = find.search(conn, tree, query) if query else None
        by_path = bool(query) and scope == "files" and _pathlike(query)
        located = find.lookup(conn, tree, query) if by_path else None
    return templates.TemplateResponse(
        request,
        "find.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "page": "search",
            "query": query,
            "scope": scope,
            "found": found,
            "located": located if located and located.files else None,
            "not_ingested": by_path and not (located and located.files),
        },
    )


def _pathlike(query: str) -> bool:
    """One word with a slash or a dot in it: a path, or the start of one."""
    return " " not in query and ("/" in query or "." in query)


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


@router.get("/ui/trees/{tree}/files")
def files_page(tree: str, path: str = "") -> Response:
    """The old Files page: now Search, narrowed to files."""
    query = urlencode({"tree": tree, "q": path, "within": "files"})
    return RedirectResponse(f"/ui/trees/{tree}/find?{query}", status_code=307)


def _count(row: find.Row) -> int:
    return 1 + sum(_count(kid) for kid in row.kids)
