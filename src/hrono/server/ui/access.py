"""The Access page (#209): who may use this server, and as what.

Admin only, at the page and at every route behind it. A page that let a writer
reach these would be a second, weaker authorization for what `/users` already
refuses them (#180).

The rules live in `hrono.auth.users`, the same functions the API calls, so the
last-admin refusal holds here because it holds there: this module draws forms
and answers with what the domain said.

A token is shown in the RESPONSE to the post that made it, and nowhere else:
not redirected to, so it is in no URL, no history entry and no access log, and
a reload re-asks the browser to post again rather than showing it a second
time. The response is `no-store` so no cache keeps it either. Only its hash is
ever stored, so there is nothing to show later.
"""

from __future__ import annotations

from urllib.parse import urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.concurrency import run_in_threadpool

from hrono.auth import users
from hrono.errors import AppError, Invalid
from hrono.server.rotation import rotate_running
from hrono.server.ui import (
    Admin,
    _fields,
    _trees,
    router,
    templates,
    write_off_loop,
)


@router.get("/ui/access", response_class=HTMLResponse)
def access_page(
    request: Request,
    user: Admin,
    tree: str = "",
    delete: str = "",
    reissue: str = "",
) -> Response:
    """Everyone with an account, and the forms to change one."""
    return _render(request, user, tree, delete=delete, reissue=reissue)


@router.post("/ui/access/create")
async def create(request: Request, user: Admin) -> Response:
    form = await _fields(request)
    name = form.get("name", "").strip()
    try:
        made, token = await write_off_loop(
            request.app.state.db,
            lambda conn: users.create_user(conn, name, form.get("role", "")),
        )
    except AppError as exc:
        return _refused(request, user, form, exc, typed=name)
    return _render(
        request,
        user,
        form.get("tree", ""),
        issued={"name": made.name, "role": made.role, "token": token},
    )


@router.post("/ui/access/{name}/role")
async def re_role(request: Request, user: Admin, name: str) -> Response:
    form = await _fields(request)
    try:
        changed = await write_off_loop(
            request.app.state.db,
            lambda conn: users.set_role(conn, name, form.get("role", "")),
        )
    except AppError as exc:
        return _refused(request, user, form, exc)
    return _settled(form, done=f"{changed.name} is now {changed.role}")


@router.post("/ui/access/{name}/reissue")
async def reissue(request: Request, user: Admin, name: str) -> Response:
    form = await _fields(request)
    if not form.get("confirm"):
        return _refused(
            request, user, form, Invalid(f"confirm to reissue: {name}")
        )
    try:
        changed, token = await write_off_loop(
            request.app.state.db, lambda conn: users.reset_token(conn, name)
        )
    except AppError as exc:
        return _refused(request, user, form, exc)
    return _render(
        request,
        user,
        form.get("tree", ""),
        issued={"name": changed.name, "role": changed.role, "token": token},
    )


@router.post("/ui/access/{name}/delete")
async def remove(request: Request, user: Admin, name: str) -> Response:
    form = await _fields(request)
    if not form.get("confirm"):
        return _refused(
            request, user, form, Invalid(f"confirm to delete: {name}")
        )
    try:
        gone = await write_off_loop(
            request.app.state.db, lambda conn: users.delete_user(conn, name)
        )
    except AppError as exc:
        return _refused(request, user, form, exc)
    if not gone:
        return _refused(request, user, form, Invalid(f"user not found: {name}"))
    return _settled(form, done=f"deleted {name}")


@router.post("/ui/access/rotate-key")
async def rotate_key(request: Request, user: Admin) -> Response:
    """Re-encrypt every stored secret under a new master key (#177)."""
    form = await _fields(request)
    if not form.get("confirm"):
        return _refused(
            request, user, form, Invalid("confirm to rotate the master key")
        )
    try:
        result = await run_in_threadpool(
            rotate_running,
            request.app,
            form.get("old_key", "").strip().encode(),
            form.get("new_key", "").strip().encode(),
        )
    except AppError as exc:
        return _refused(request, user, form, exc)
    return _render(
        request,
        user,
        form.get("tree", ""),
        rotated={"rows": result.rows, "key_id": result.key_id},
    )


def _settled(form: dict[str, str], *, done: str) -> Response:
    """Redirect-after-POST for a change that has no secret to show."""
    query = urlencode({"tree": form.get("tree", ""), "done": done})
    return RedirectResponse(f"/ui/access?{query}", status_code=303)


def _refused(
    request: Request,
    user: users.User,
    form: dict[str, str],
    error: AppError,
    *,
    typed: str = "",
) -> Response:
    return _render(
        request,
        user,
        form.get("tree", ""),
        error=error.message,
        typed=typed,
        status=error.status_code,
    )


def _render(
    request: Request,
    user: users.User,
    tree: str,
    *,
    delete: str = "",
    reissue: str = "",
    issued: dict[str, str] | None = None,
    rotated: dict[str, int] | None = None,
    error: str = "",
    typed: str = "",
    status: int = 200,
) -> Response:
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        everyone = users.list_users(conn)
    answer = templates.TemplateResponse(
        request,
        "access.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree if tree in trees else trees[0],
            "people": everyone,
            "roles": sorted(users.ROLES),
            "delete": delete,
            "reissue": reissue,
            "issued": issued,
            "rotated": rotated,
            "error": error,
            "typed": typed,
        },
        status_code=status,
    )
    answer.headers["Cache-Control"] = "no-store"
    return answer
