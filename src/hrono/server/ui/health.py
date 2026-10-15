"""The Health page: what is wrong, and the fix beside it.

The reading is for everyone who can sign in. Every write here is the admin
door the same operation has everywhere else (`edits`, `POST /jobs`): a page
that took a lesser role would be a weaker second authorization for it.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, replace
from urllib.parse import quote, urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from hrono import edits
from hrono.cluster.recipe import MIN_POINTS
from hrono.errors import AppError, DomainError
from hrono.health import attention, report, triage
from hrono.jobs.worker import enqueue
from hrono.server.i18n import gettext as _
from hrono.server.i18n import ngettext as n_
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
from hrono.server.ui.nodes import refusal


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
    items = tuple(_shown(item) for item in kept.items) if kept else ()
    context = {
        "checked_at": clock(kept.checked_at) if kept is not None else "",
        "checked": kept is not None,
        "checking": checking,
        "parked_total": kept.parked_total if kept is not None else 0,
        "parked": kept.parked if kept is not None else (),
        "misfit_total": kept.misfit_total if kept is not None else 0,
        "misfits": kept.misfits if kept is not None else (),
        "stale": tuple(replace(row, why=_why(row.why)) for row in kept.stale)
        if kept is not None
        else (),
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
        return _here(tree, error=_("choose a topic"))
    try:
        await write_off_loop(
            request.app.state.db,
            lambda conn: edits.move_section(
                conn, tree, int(section), int(target)
            ),
        )
    except (AppError, DomainError) as exc:
        return _here(tree, error=refusal(exc))
    await run_in_threadpool(report.refresh, request.app.state.db, tree)
    return _here(
        tree,
        done=_(
            "section {section} filed in topic {topic}",
            section=section,
            topic=target,
        ),
    )


@router.post("/ui/trees/{tree}/triage/regenerate")
async def regenerate_from_health(
    tree: str, request: Request, user: Admin
) -> Response:
    """Rewrite ONE topic's brief: the same op a sync runs, scoped to it."""
    fields = await _fields(request)
    node = fields.get("node", "")
    if not node.isdigit():
        return _here(tree, error=_("choose a topic"))
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
        return _here(tree, error=refusal(exc))
    op = "brief" if level == 0 else "brief-upper"
    started = enqueue(
        request.app.state.db,
        op,
        {"node": int(node), "level": level},
        tree=tree,
        started_by=user.name,
    )
    said = _("Rewriting the brief of topic {id}.", id=node)
    return RedirectResponse(
        f"/ui/jobs?tree={tree}&done={quote(said)}&run={started}",
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
        return _here(tree, error=_("choose an edit to release"))
    try:
        await write_off_loop(
            request.app.state.db,
            lambda conn: attention.release(conn, tree, kind, int(target)),
        )
    except AppError as exc:
        return _here(tree, error=refusal(exc))
    await run_in_threadpool(report.refresh, request.app.state.db, tree)
    return _here(tree, done=_("handed back to automation"))


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


@dataclass(frozen=True)
class Shown:
    """One check as the page says it, in the reader's language."""

    count: int
    said: str
    detail: str
    link: str


def _shown(item: triage.Item) -> Shown:
    """A stored check's sentence and detail, said in the page's language.

    The report stores the English (it is the API's too); the page picks the
    sentence again by the check's kind, so a count agrees with its noun.
    """
    n, said, detail = item.count, item.said, item.detail
    if item.kind == "topics cut off from the root":
        said = n_(
            n,
            "{n} topic is cut off from the root",
            "{n} topics are cut off from the root",
        )
        if not n:
            said = _("Every topic can be reached from the root")
        detail = _("Everything beneath them is missing from the export.")
    elif item.kind == "topics with no usable brief, or a stale one":
        said = n_(
            n,
            "{n} topic has no usable brief, or a stale one",
            "{n} topics have no usable brief, or a stale one",
        )
        if not n:
            said = _("Every topic has a brief that holds")
        people = re.search(r"; (\d+) needs? a person\.$", detail)
        detail = (
            n_(
                int(people.group(1)),
                "Recall cannot answer from them until they are rewritten; {n} needs a person.",  # noqa: E501
                "Recall cannot answer from them until they are rewritten; {n} need a person.",  # noqa: E501
            )
            if people
            else _("Recall cannot answer from them until a sync rewrites them.")
        )
    elif item.kind == "sections waiting for a topic":
        said = n_(
            n,
            "{n} section is waiting for a topic",
            "{n} sections are waiting for a topic",
        )
        if not n:
            said = _("No sections are waiting for a topic")
        detail = _("Read and embedded, but not on the map yet.")
    elif item.kind == "sections placed without a score":
        said = n_(
            n,
            "{n} section was placed without a score",
            "{n} sections were placed without a score",
        )
        if not n:
            said = _("Every section was placed by a score")
        detail = _("Filed by rule rather than matched to a topic.")
    elif item.kind == "runs that failed":
        said = n_(n, "{n} run has failed", "{n} runs have failed")
        if not n:
            said = _("No run has failed")
        detail = _("Open Runs for the code and message each one failed with.")
    return Shown(count=n, said=said, detail=detail, link=item.link)


def _why(why: str) -> str:
    """Why a brief is listed (`briefs.stale_why`), in the page's language."""
    if why == "it has no brief yet":
        return _("it has no brief yet")
    if why == "something beneath it changed since it was written":
        return _("something beneath it changed since it was written")
    if why == "its members changed since it was written":
        return _("its members changed since it was written")
    if why == "its prompt or model changed since it was written":
        return _("its prompt or model changed since it was written")
    inner = re.fullmatch(r"what was stored is not a brief \((.*)\)", why, re.S)
    if inner:
        return _("what was stored is not a brief ({why})", why=inner.group(1))
    return why


def _here(tree: str, **outcome: str) -> Response:
    query = urlencode({"tree": tree, **{k: v for k, v in outcome.items() if v}})
    return RedirectResponse(f"/ui/trees/{tree}/triage?{query}", status_code=303)
