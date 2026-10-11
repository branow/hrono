"""The Health page: what is wrong, and the fix beside it.

The reading is for everyone who can sign in. Every write here is the admin
door the same operation has everywhere else (`edits`, `POST /jobs`): a page
that took a lesser role would be a weaker second authorization for it.
"""

from __future__ import annotations

import sqlite3
from urllib.parse import quote, urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from hrono import edits
from hrono.cluster.recipe import MIN_POINTS
from hrono.errors import AppError, DomainError
from hrono.health import attention, report, triage
from hrono.jobs.worker import enqueue
from hrono.server.ui import (
    Admin,
    Reader,
    _fields,
    _trees,
    read_off_loop,
    router,
    templates,
    write_off_loop,
)
from hrono.server.ui.jobs import clock


@router.get("/ui/trees/{tree}/triage", response_class=HTMLResponse)
def triage_page(tree: str, request: Request, user: Reader) -> Response:
    """What is wrong with this tree, counted, and each kind listed.

    Read from the stored report (``health.report``): the checks run when the
    tree changes and on Recheck, never on opening the page.
    """
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        kept = report.load(conn, tree)
        checking = _checking(conn, tree)
    items = kept.items if kept is not None else ()
    context = {
        "checked_at": clock(kept.checked_at) if kept is not None else "",
        "checked": kept is not None,
        "checking": checking,
        "parked_total": kept.parked_total if kept is not None else 0,
        "parked": kept.parked if kept is not None else (),
        "misfit_total": kept.misfit_total if kept is not None else 0,
        "misfits": kept.misfits if kept is not None else (),
        "stale": kept.stale if kept is not None else (),
        "held": kept.held if kept is not None else (),
        "topics": kept.topics if kept is not None else (),
    }
    return templates.TemplateResponse(
        request,
        "triage.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "items": items,
            "clean": kept is not None and triage.clean(items),
            "can_write": user.role == "admin",
            "shown": attention.SHOWN,
            "min_points": MIN_POINTS,
            **context,
        },
    )


@router.post("/ui/trees/{tree}/triage/place")
async def place_from_health(
    tree: str, request: Request, user: Admin
) -> Response:
    """File a waiting or misfit section in the chosen topic; it is pinned
    there by `edits.move_section`, so a sync leaves it where a person put it."""
    fields = await _fields(request)
    section, target = fields.get("section", ""), fields.get("to_node", "")
    if not (section.isdigit() and target.isdigit()):
        return _here(tree, error="choose a topic")
    try:
        await write_off_loop(
            request.app.state.db,
            lambda conn: edits.move_section(
                conn, tree, int(section), int(target)
            ),
        )
    except (AppError, DomainError) as exc:
        return _here(tree, error=str(exc))
    await run_in_threadpool(report.refresh, request.app.state.db, tree)
    return _here(tree, done=f"section {section} filed in topic {target}")


@router.post("/ui/trees/{tree}/triage/regenerate")
async def regenerate_from_health(
    tree: str, request: Request, user: Admin
) -> Response:
    """Rewrite ONE topic's brief: the same op a sync runs, scoped to it."""
    fields = await _fields(request)
    node = fields.get("node", "")
    if not node.isdigit():
        return _here(tree, error="choose a topic")
    try:

        def _level(conn: object) -> int:
            edits.require_node(conn, tree, int(node))
            return int(
                conn.execute(  # type: ignore[attr-defined]
                    "SELECT level FROM nodes WHERE id = ?", (int(node),)
                ).fetchone()["level"]
            )

        level = await read_off_loop(request.app.state.db, _level)
    except AppError as exc:
        return _here(tree, error=str(exc))
    op = "brief" if level == 0 else "brief-upper"
    started = enqueue(
        request.app.state.db,
        op,
        {"node": int(node), "level": level},
        tree=tree,
        started_by=user.name,
    )
    return RedirectResponse(
        f"/ui/jobs?tree={tree}"
        f"&done={quote(f'Rewriting the brief of topic {node}.')}&run={started}",
        status_code=303,
    )


@router.post("/ui/trees/{tree}/triage/release")
async def release_from_health(
    tree: str, request: Request, user: Admin
) -> Response:
    """Hand one held edit back to automation."""
    fields = await _fields(request)
    kind, target = fields.get("kind", ""), fields.get("target", "")
    if not target.isdigit():
        return _here(tree, error="choose an edit to release")
    try:
        await write_off_loop(
            request.app.state.db,
            lambda conn: attention.release(conn, tree, kind, int(target)),
        )
    except AppError as exc:
        return _here(tree, error=str(exc))
    await run_in_threadpool(report.refresh, request.app.state.db, tree)
    return _here(tree, done="handed back to automation")


@router.post("/ui/trees/{tree}/triage/recheck")
def recheck_from_health(tree: str, request: Request, user: Admin) -> Response:
    """Work the report out again in the background; the page shows it
    checking and reloads itself when the run ends."""
    enqueue(request.app.state.db, "health", {}, tree=tree, started_by=user.name)
    return _here(tree)


def _checking(conn: sqlite3.Connection, tree: str) -> str:
    """The id of a health run for ``tree`` still waiting or working, or ""."""
    row = conn.execute(
        "SELECT id FROM jobs WHERE op = 'health' AND tree = ? "
        "AND status IN ('pending', 'running') ORDER BY created_at DESC LIMIT 1",
        (tree,),
    ).fetchone()
    return str(row["id"]) if row else ""


def _here(tree: str, **outcome: str) -> Response:
    query = urlencode({"tree": tree, **{k: v for k, v in outcome.items() if v}})
    return RedirectResponse(f"/ui/trees/{tree}/triage?{query}", status_code=303)
