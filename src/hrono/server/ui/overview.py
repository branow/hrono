"""The dashboard's front page, and the one button on it (#180).

The page answers "what state is this tree in" before it offers anything to do
about it, so everything here is a READ that some other page already owns: the
attention list is `triage.survey`, the runs are `jobs.store`, the shape is
`_shape`. A landing page that computed its own numbers would be a second set of
numbers to disagree with the pages they link to.
"""

from __future__ import annotations

import sqlite3

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from hrono.cluster import incubator
from hrono.jobs import store as job_store
from hrono.jobs.worker import enqueue
from hrono.registry import store as registry_store
from hrono.server import triage
from hrono.server.ui import Reader, Writer, _shape, _trees, router, templates
from hrono.server.ui.jobs import clock

# Three is enough to see whether the last thing that ran worked, which is the
# only question this page asks of the run log; the rest is the runs page.
RECENT_RUNS = 3


@router.get("/ui", response_class=HTMLResponse)
def overview(request: Request, user: Reader, tree: str = "") -> Response:
    """The shell: which tree, who you are, and what this tree holds."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        chosen = tree if tree in trees else trees[0]
        topics, levels = _shape(conn, chosen)
        attention = triage.survey(conn, chosen)
        shape = {
            "topics": topics,
            "levels": levels,
            "leaves": _leaves(conn, chosen),
            "filed": _filed(conn, chosen),
            "parked": incubator.count(conn, chosen),
        }
        runs = _recent(conn, chosen)
        sources = len(registry_store.list_all(conn, "sources"))
    return templates.TemplateResponse(
        request,
        "overview.html",
        {
            "user": user,
            "trees": trees,
            "tree": chosen,
            "topics": topics,
            "levels": levels,
            "shape": shape,
            "attention": [item for item in attention if item.count],
            "clean": triage.clean(attention),
            "runs": runs,
            "sources": sources,
            # a control a reader cannot use is not shown AND not accepted: a
            # button nobody can see is not a permission (#180)
            "can_write": user.role in {"writer", "admin"},
        },
    )


def _leaves(conn: sqlite3.Connection, tree: str) -> int:
    """Level-0 topics — the ones that hold chunks rather than other topics."""
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE tree = ? AND level = 0",
            (tree,),
        ).fetchone()[0]
    )


def _filed(conn: sqlite3.Connection, tree: str) -> int:
    """Chunks that have landed in a topic — what the map actually covers."""
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM node_members m "
            "JOIN nodes n ON n.id = m.node_id WHERE n.tree = ?",
            (tree,),
        ).fetchone()[0]
    )


def _recent(conn: sqlite3.Connection, tree: str) -> list[dict[str, object]]:
    """The last few top-level runs, newest first."""
    rows = [
        row
        for row in job_store.list_jobs(conn)
        if (row["tree"] or "default") == tree and row["parent_id"] is None
    ]
    return [
        {
            "op": str(row["op"]),
            "status": str(row["status"]),
            "when": clock(str(row["created_at"])),
        }
        for row in reversed(rows[-RECENT_RUNS:])
    ]


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
