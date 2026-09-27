"""Signing in and out of the dashboard (#180).

The browser carries the SAME token the CLI does, in an HttpOnly SameSite=Strict
cookie. SameSite=Strict is also this dashboard's CSRF answer: a cross-site POST
does not carry the cookie, which is why the write routes elsewhere in this
package need no token of their own (#188).
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from hrono.auth.users import authenticate
from hrono.server.auth import COOKIE
from hrono.server.ui import COOKIE_MAX_AGE, _fields, router, templates


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
