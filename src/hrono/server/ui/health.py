"""The Health page: what is wrong, and the fix beside it (E009, #218).

The reading is for everyone who can sign in. Every write here is the admin
door the same operation has everywhere else (`edits`, `POST /jobs`): a page
that took a lesser role would be a weaker second authorization for it.
"""

from __future__ import annotations

from urllib.parse import quote, urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from hrono import edits
from hrono.cluster.incubator import MAX_AGE
from hrono.cluster.recipe import MIN_POINTS
from hrono.embed.model import resolve_embedding_model
from hrono.errors import AppError, DomainError
from hrono.jobs.worker import enqueue
from hrono.server import attention, triage
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


@router.get("/ui/trees/{tree}/triage", response_class=HTMLResponse)
def triage_page(tree: str, request: Request, user: Reader) -> Response:
    """What is wrong with this tree, counted, and each kind listed."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        items = triage.survey(conn, tree)
        model = _model(conn)
        parked_total, parked = attention.waiting(conn, tree, model)
        misfit_total, misfit = attention.misfits(conn, tree, model)
        context = {
            "parked_total": parked_total,
            "parked": parked,
            "misfit_total": misfit_total,
            "misfits": misfit,
            "stale": attention.stale(conn, tree),
            "held": attention.held(conn, tree),
            "topics": attention.topics(conn, tree),
        }
    return templates.TemplateResponse(
        request,
        "triage.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "items": items,
            "clean": triage.clean(items),
            "can_write": user.role == "admin",
            "shown": attention.SHOWN,
            "max_age": MAX_AGE,
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
    return _here(tree, done="handed back to automation")


def _here(tree: str, **outcome: str) -> Response:
    query = urlencode({"tree": tree, **{k: v for k, v in outcome.items() if v}})
    return RedirectResponse(f"/ui/trees/{tree}/triage?{query}", status_code=303)


def _model(conn: object) -> str | None:
    try:
        return str(resolve_embedding_model(conn, {})["name"])  # type: ignore[arg-type]
    except (AppError, DomainError):
        return None
