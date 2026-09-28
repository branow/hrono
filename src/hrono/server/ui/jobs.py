"""What has run and what is running (#181, T53).

A parent's status and progress are DERIVED from its children at read time
(#172), so nothing here stores a number that can go stale.
"""

from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from hrono.errors import NotFound
from hrono.jobs import store as job_store
from hrono.jobs.aggregate import rollup, total_spend
from hrono.jobs.cancel import cancel
from hrono.jobs.model import to_job
from hrono.server.ui import Reader, Writer, _trees, router, templates

_LIVE = frozenset({"pending", "running", "partial"})


@router.get("/ui/jobs", response_class=HTMLResponse)
def jobs_view(request: Request, user: Reader, tree: str = "") -> Response:
    """The tree's runs: what each is doing, spending, and made of."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        chosen = tree if tree in trees else trees[0]
        rows = [
            row
            for row in job_store.list_jobs(conn)
            if (row["tree"] or "default") == chosen and row["parent_id"] is None
        ]
        jobs = [_render_job(conn, row) for row in reversed(rows)]
    return templates.TemplateResponse(
        request,
        "jobs.html",
        {
            "user": user,
            "trees": trees,
            "tree": chosen,
            "jobs": jobs,
            "can_write": user.role in {"writer", "admin"},
            "notice": request.query_params.get("notice"),
        },
    )


def _render_job(conn: object, row: object) -> dict[str, object]:
    """One run, as the page needs it: derived status, progress, spend, kids.

    The same derivations the API serves (#172, #179) rather than a second set
    for the page — a dashboard that computes its own status is a dashboard that
    disagrees with `hrono jobs get`.
    """
    children = job_store.children(conn, str(row["id"]))  # type: ignore[arg-type,index]
    rolled = rollup([str(child["status"]) for child in children])
    job = to_job(row)  # type: ignore[arg-type]
    spent = (
        total_spend([to_job(child).result for child in children])
        if children
        else total_spend([job.result])
    )
    status = rolled.status if rolled is not None else job.status
    return {
        "id": job.id,
        "short_id": job.id.removeprefix("job_")[:8],
        "started": _clock(job.created_at),
        "took": _elapsed(job.created_at, job.updated_at, live=status in _LIVE),
        "op": job.op,
        "status": status,
        "live": status in _LIVE,
        "progress": (
            {"done": rolled.done, "total": rolled.total}
            if rolled is not None
            else None
        ),
        "cost": spent,
        "error": (
            {"code": job.error_code or "internal-error", "message": job.error}
            if job.error
            else None
        ),
        "children": [
            {
                "op": str(child["op"]),
                "status": str(child["status"]),
                "scope": to_job(child).scope,
            }
            for child in children
        ],
    }


def _clock(stamp: str) -> str:
    """The time of day a run started. Three `maintain` rows with no clock on
    them are three indistinguishable rows."""
    moment = _parsed(stamp)
    return "" if moment is None else moment.strftime("%d %b %H:%M")


def _elapsed(start: str, end: str, *, live: bool) -> str:
    """How long it took, or how long it has been going."""
    began, ended = _parsed(start), _parsed(end)
    if began is None or ended is None:
        return ""
    seconds = int(
        ((datetime.now(UTC) if live else ended) - began).total_seconds()
    )
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m {seconds % 60:02d}s"
    return f"{seconds // 3600}h {(seconds % 3600) // 60:02d}m"


def _parsed(stamp: str) -> datetime | None:
    try:
        return datetime.fromisoformat(stamp)
    except ValueError:
        return None


@router.post("/ui/jobs/{job_id}/cancel")
def cancel_from_the_page(
    job_id: str, request: Request, user: Writer, tree: str = ""
) -> Response:
    """Cancel from the page, and say what could not be stopped (#173)."""
    with request.app.state.db.write() as conn:
        if job_store.get(conn, job_id) is None:
            raise NotFound(f"job not found: {job_id}")
        outcome = cancel(conn, job_id)
    notice = f"stopped {outcome.stopped}"
    if outcome.running:
        notice += f"; {outcome.running} already running and will finish"
    return RedirectResponse(
        f"/ui/jobs?tree={tree or 'default'}&notice={quote(notice)}",
        status_code=303,
    )
