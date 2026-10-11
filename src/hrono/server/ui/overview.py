"""The dashboard's front page, and the one button on it.

The page answers four questions before it offers anything to do about them —
is the tree up to date with its sources, is anything running, does anything
need a person, what did the last run do — so everything here is a READ that
some other page already owns: the sources are `freshness.survey`, the attention
list is `triage.survey`, the runs are the runs page's own `render_job`, the
shape is `_shape`. A landing page that computed its own numbers would be a
second set of numbers to disagree with the pages they link to.
"""

from __future__ import annotations

import sqlite3
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from hrono.cluster import incubator
from hrono.health import report, triage
from hrono.jobs import store as job_store
from hrono.jobs.worker import enqueue
from hrono.server import freshness
from hrono.server.ui import Reader, Writer, _shape, _trees, router, templates
from hrono.server.ui.jobs import clock, render_job
from hrono.server.ui.setup import progress
from hrono.server.ui.spend import describe
from hrono.usage.rollup import Filter, recorded_since, total

# Enough runs to find the one that is going and the last one that finished.
RECENT_RUNS = 5

# What each state of a source is called on the page, and how loudly.
STATES = {
    "current": ("up to date", "ok"),
    "behind": ("behind", "warn"),
    "unread": ("never read", "warn"),
    "unreachable": ("could not check", "plain"),
    "not-compared": ("not compared", "plain"),
}


@router.get("/ui", response_class=HTMLResponse)
def overview(request: Request, user: Reader, tree: str = "") -> Response:
    """Is it up to date, is anything running, what needs me, what did it do."""
    database = request.app.state.db
    with database.connect() as conn:
        trees = _trees(conn)
        chosen = tree if tree in trees else trees[0]
        topics, levels = _shape(conn, chosen)
        kept = report.load(conn, chosen)
        attention = kept.items if kept is not None else ()
        shape = {
            "topics": topics,
            "levels": levels,
            "leaves": _leaves(conn, chosen),
            "filed": _filed(conn, chosen),
            "parked": incubator.count(conn, chosen),
        }
        runs = _recent(conn, chosen)
        spent = describe(total(conn, Filter(tree=chosen)))
        started = not topics and any(progress(conn, chosen).done.values())
    sources = [
        {
            "name": one.name,
            "kind": one.kind,
            "read": clock(one.read_at or ""),
            "commit": (one.commit or "")[:8],
            "state": one.state,
            "said": STATES[one.state][0],
            "tone": STATES[one.state][1],
        }
        for one in freshness.survey(
            database,
            request.app.state.cipher,
            request.app.state.heads,
            chosen,
        )
    ]
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
            "spent": spent,
            "setup_started": started,
            "attention": [item for item in attention if item.count],
            "clean": kept is not None and triage.clean(attention),
            "checked": kept is not None,
            "running": [run for run in runs if run["live"]],
            "last": next((run for run in runs if not run["live"]), None),
            "source_states": sources,
            "behind": sum(1 for one in sources if one["state"] == "behind"),
            "sources": len(sources),
            # a control a reader cannot use is not shown AND not accepted: a
            # button nobody can see is not a permission
            "can_write": user.role in {"writer", "admin"},
        },
    )


def _leaves(conn: sqlite3.Connection, tree: str) -> int:
    """Level-0 topics — the ones that hold sections rather than other topics."""
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
    """The last few top-level runs, newest first, as the runs page reads them.

    The same derivation the runs page uses (`render_job`), so home and Runs
    cannot give two answers about one run.
    """
    since = recorded_since(conn)
    return [
        render_job(conn, row, since)
        for row in job_store.page_roots(conn, tree, limit=RECENT_RUNS, offset=0)
    ]


@router.post("/ui/trees/{tree}/sync")
def sync_from_the_page(tree: str, request: Request, user: Writer) -> Response:
    """Start a sync from the dashboard and come back to the page.

    A WRITER dependency, not a hidden button: the control is absent from a
    reader's HTML and refused by this route if they post it anyway. Hiding it
    is courtesy; this is the permission.

    Redirect-after-POST so a refresh does not start a second run.
    """
    started = enqueue(
        request.app.state.db, "sync-tree", {}, tree=tree, started_by=user.name
    )
    said = quote(
        "Started a sync. It reads every source and files what changed."
    )
    return RedirectResponse(
        f"/ui?tree={tree}&done={said}&run={started}", status_code=303
    )
