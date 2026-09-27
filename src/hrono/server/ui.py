"""The dashboard shell: server-rendered, logged in, role-gated (T49, #180).

Jinja and plain HTML, served by the same process that owns the database — so
the dashboard ships inside the one `hrono` binary with no build step and no
second release artifact. The stakeholder chose that on 2026-09-27.

Authentication is the API's, not a second system: the browser carries the SAME
token the CLI uses, in an HttpOnly SameSite=Strict cookie, resolved by the same
``require_role`` dependency every API route uses. What differs is only the
FAILURE — an API caller gets a 401, a browser gets the login page, because a
401 in a tab is a dead end.
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qs, quote

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from hrono.auth.users import User, authenticate
from hrono.errors import AppError, NotFound
from hrono.jobs import store as job_store
from hrono.jobs.aggregate import rollup, total_spend
from hrono.jobs.cancel import cancel
from hrono.jobs.model import to_job
from hrono.jobs.worker import enqueue
from hrono.registry import store as registry_store
from hrono.server.auth import COOKIE, require_role

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# A year is wrong and an hour is annoying. A day is the shape of an operator's
# session with a tool they open to look at something.
COOKIE_MAX_AGE = 60 * 60 * 24


async def _fields(request: Request) -> dict[str, str]:
    """An HTML form's fields, from the standard library.

    Not `request.form()` and not `Form(...)`: both require `python-multipart`,
    even for the urlencoded body a plain HTML form actually sends. `parse_qs`
    is in the standard library and reads exactly that, so the whole dashboard
    costs no dependency for its forms. The day one needs a FILE upload is the
    day multipart earns its place.
    """
    body = (await request.body()).decode("utf-8", "replace")
    return {
        key: values[0]
        for key, values in parse_qs(body, keep_blank_values=True).items()
    }


class LoginRequired(AppError):
    """A browser reached a page without a usable cookie (#180).

    Its own type so the shell can answer with the login PAGE while the API
    keeps answering 401. Same authentication, different dead end.
    """

    status_code = 307
    code = "login-required"


def _viewer(minimum: str):
    """Resolve the cookie through the API's own role check, for a page."""

    def dependency(request: Request) -> User:
        try:
            return require_role(minimum)(request)
        except AppError as exc:
            if exc.status_code == 401:
                raise LoginRequired("sign in") from exc
            raise

    return dependency


Reader = Annotated[User, Depends(_viewer("reader"))]
Writer = Annotated[User, Depends(_viewer("writer"))]


@router.get("/ui/login", response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/ui/login")
async def sign_in(request: Request) -> Response:
    """Take the API token and keep it in a cookie the page cannot read.

    A wrong token re-renders the form rather than redirecting: the operator has
    the thing they typed in front of them, which is where a correction starts.
    """
    token = (await _fields(request)).get("token", "")
    with request.app.state.db.connect() as conn:
        user = authenticate(conn, token) if token else None
    if user is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "that token was not accepted"},
            status_code=401,
        )
    answer = RedirectResponse("/ui", status_code=303)
    answer.set_cookie(
        COOKIE,
        token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,  # page scripts cannot read it
        samesite="strict",  # another site cannot cause it to be sent
        secure=request.url.scheme == "https",  # and http still works locally
    )
    return answer


@router.post("/ui/logout")
def sign_out() -> Response:
    answer = RedirectResponse("/ui/login", status_code=303)
    answer.delete_cookie(COOKIE)
    return answer


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


def _trees(conn: object) -> list[str]:
    """Every declared tree (#054), or `default` when none are.

    A database nobody has partitioned still has exactly one tree, and the
    switcher should say so rather than be empty.
    """
    declared = [
        str(row["name"])
        for row in registry_store.list_all(conn, "trees")  # type: ignore[arg-type]
    ]
    return declared or ["default"]


def _shape(conn: object, tree: str) -> tuple[int, int]:
    row = conn.execute(  # type: ignore[attr-defined]
        "SELECT COUNT(*) AS topics, COALESCE(MAX(level), 0) AS top "
        "FROM nodes WHERE tree = ?",
        (tree,),
    ).fetchone()
    return int(row["topics"]), int(row["top"]) + 1 if row["topics"] else 0
