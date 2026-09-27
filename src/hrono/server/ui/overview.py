"""The dashboard's front page, and the one button on it (#180)."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from hrono.jobs.worker import enqueue
from hrono.server.ui import Reader, Writer, _shape, _trees, router, templates


@router.get("/ui", response_class=HTMLResponse)
def overview(request: Request, user: Reader, tree: str = "") -> Response:
    """The shell: which tree, who you are, and what this tree holds."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        chosen = tree if tree in trees else trees[0]
        topics, levels = _shape(conn, chosen)
    return templates.TemplateResponse(
        request,
        "overview.html",
        {
            "user": user,
            "trees": trees,
            "tree": chosen,
            "topics": topics,
            "levels": levels,
            # a control a reader cannot use is not shown AND not accepted: a
            # button nobody can see is not a permission (#180)
            "can_write": user.role in {"writer", "admin"},
        },
    )


@router.post("/ui/trees/{tree}/sync")
def sync_from_the_page(tree: str, request: Request, user: Writer) -> Response:
    """Start a sync from the dashboard and come back to the page.

    A WRITER dependency, not a hidden button: the control is absent from a
    reader's HTML and refused by this route if they post it anyway. Hiding it
    is courtesy; this is the permission.

    Redirect-after-POST so a refresh does not start a second run.
    """
    enqueue(request.app.state.db, "sync-tree", {}, tree=tree)
    return RedirectResponse(f"/ui?tree={tree}", status_code=303)
