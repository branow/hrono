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
from hrono.jobs.ops import OPS
from hrono.jobs.scope import SOURCE_SCOPED, fan_out, fans_out
from hrono.jobs.worker import enqueue
from hrono.registry import store as registry_store
from hrono.server import outcome
from hrono.server.ui import (
    Admin,
    Reader,
    Writer,
    _trees,
    router,
    templates,
)
from hrono.server.ui import (
    _fields as _form_fields,
)

_LIVE = frozenset({"pending", "running", "partial"})

# An op name is the API's word and the CLI's word, so the page keeps it — but
# an operator reading a run log should not have to already know what
# `cluster-briefs` does. The name stays, and this says it in a sentence.
MEANS = {
    "sync-tree": "the NORMAL one: re-read the sources and change only what the "
    "changes touched",
    "sync": "fetch a source's files",
    "split": "cut the files into sections",
    "embed": "turn sections into vectors",
    "condense": "shorten each section so it can be summarised",
    "cluster": "group sections into topics",
    "cluster-briefs": "group topics into higher-level topics",
    "brief": "write a summary for each topic that holds sections",
    "brief-upper": "write a summary for each topic that groups topics",
    "build-tree": "throw the tree away and build it again from nothing — "
    "every section re-condensed, every brief rewritten, every model call paid "
    "for twice",
    "update": "re-file only what changed",
    "propagate": "mark the summaries a change has invalidated",
    "maintain": "the FIRST one: ingest the sources and build a tree that does "
    "not exist yet. On a tree that does, it fills in what is missing",
    "monitor": "look for topics that have drifted out of shape",
    "repair": "split, merge or retire the topics that drifted",
    "settle": "place the sections that were still waiting",
    "noop": "do nothing — a health check of the worker",
}

# The order an operator meets the stages in, so the list of things they may run
# reads as the pipeline rather than as `sorted(OPS)`. Anything registered and
# not named here still appears, after these — a new op is runnable the day it
# exists, which is the whole point of driving this off `OPS` (#200).
ORDER = (
    "sync-tree",
    "maintain",
    "sync",
    "split",
    "embed",
    "condense",
    "cluster",
    "cluster-briefs",
    "brief",
    "brief-upper",
    "build-tree",
    "update",
    "propagate",
    "monitor",
    "repair",
    "settle",
    "noop",
)
# Running a stage out of order can leave a tree that looks right and is wrong
# (`server/jobs.py`), so the two that compose the others in the correct order
# are offered first and marked, and the rest are behind a disclosure.
WHOLE = ("sync-tree", "maintain", "build-tree")


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
        sources = [
            str(row["name"]) for row in registry_store.list_all(conn, "sources")
        ]
    return templates.TemplateResponse(
        request,
        "jobs.html",
        {
            "user": user,
            "trees": trees,
            "tree": chosen,
            "jobs": jobs,
            "runnable": _runnable(),
            "sources": sources,
            "can_write": user.role in {"writer", "admin"},
            "can_run": user.role == "admin",
            "notice": request.query_params.get("notice"),
        },
    )


def _runnable() -> list[dict[str, object]]:
    """Every registered op, in pipeline order, with what it does and takes.

    Read off `OPS` rather than listed by hand: the dashboard offering a subset
    of what the tool can do was the gap — one `sync` button over sixteen ops,
    so regenerating just the condensations meant reaching for the API (#200).
    """
    known = {name: index for index, name in enumerate(ORDER)}
    return [
        {
            "op": name,
            "means": MEANS.get(name, ""),
            "whole": name in WHOLE,
            "per_source": name in SOURCE_SCOPED,
        }
        for name in sorted(
            OPS, key=lambda name: (known.get(name, len(ORDER)), name)
        )
    ]


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
    did = outcome.read(job.result)
    return {
        "outcome": did,
        "id": job.id,
        "short_id": job.id.removeprefix("job_")[:8],
        "started": clock(job.created_at),
        "took": _elapsed(job.created_at, job.updated_at, live=status in _LIVE),
        "op": job.op,
        "means": MEANS.get(job.op, ""),
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
                "means": MEANS.get(str(child["op"]), ""),
                "status": str(child["status"]),
                "scope": to_job(child).scope,
                "outcome": outcome.read(to_job(child).result),
                "error": to_job(child).error or "",
            }
            for child in children
        ],
    }


def clock(stamp: str) -> str:
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


@router.get("/ui/jobs/{job_id}", response_class=HTMLResponse)
def one_run(
    job_id: str, request: Request, user: Reader, tree: str = ""
) -> Response:
    """ONE run, in full — what it did, what it is doing, and every piece of it.

    The list cannot be the whole surface: a row has to fit in a column, so the
    detail that answers "what is it doing right now" and "what exactly did each
    piece find" had nowhere to be (#200). This is where a run on the front page
    and a run in the list both link to.
    """
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        row = job_store.get(conn, job_id)
        if row is None:
            raise NotFound(f"job not found: {job_id}")
        job = _render_job(conn, row)
        job["scope"] = to_job(row).scope
        job["raw"] = to_job(row).result
    return templates.TemplateResponse(
        request,
        "run.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree or str(row["tree"] or "default"),
            "job": job,
            "can_write": user.role in {"writer", "admin"},
            "can_run": user.role == "admin",
        },
    )


@router.post("/ui/jobs/run")
async def run_from_the_page(
    request: Request, user: Admin, tree: str = ""
) -> Response:
    """Run any registered op from the page — the API's own door, drawn.

    ADMIN, the role `POST /jobs` itself takes: a stage run out of order can
    leave a tree that looks right and is wrong, so this is not a softer door
    than the one it stands for.
    """
    fields = await _form_fields(request)
    op = fields.get("op", "")
    if op not in OPS:
        raise NotFound(f"unknown op: {op}")
    name = fields.get("source", "")
    scope: dict[str, object] = (
        {"type": "source", "name": name} if name else {"type": "all"}
    )
    database = request.app.state.db
    if fans_out(op, scope):
        fan_out(database, op, scope, tree=tree)
    else:
        enqueue(database, op, scope, tree=tree)
    return RedirectResponse(
        f"/ui/jobs?tree={tree or 'default'}&notice={quote(f'started {op}')}",
        status_code=303,
    )


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
