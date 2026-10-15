"""Signing in and out of the dashboard.

The browser carries the SAME token the CLI does, in an HttpOnly SameSite=Strict
cookie. SameSite=Strict is also this dashboard's CSRF answer: a cross-site POST
does not carry the cookie, which is why the write routes elsewhere in this
package need no token of their own.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from hrono.auth.users import authenticate
from hrono.server import i18n
from hrono.server.auth import COOKIE
from hrono.server.ui import (
    COOKIE_MAX_AGE,
    THEME_COOKIE,
    _fields,
    read_off_loop,
    router,
    templates,
)


@router.get("/ui/login", response_class=HTMLResponse)
def login_page(request: Request) -> Response:
    return templates.TemplateResponse(
        request, "login.html", {"rejected": False}
    )


@router.post("/ui/login")
async def sign_in(request: Request) -> Response:
    """Take the API token and keep it in a cookie the page cannot read.

    A wrong token re-renders the form rather than redirecting: the operator has
    the thing they typed in front of them, which is where a correction starts.
    """
    token = (await _fields(request)).get("token", "")
    user = (
        await read_off_loop(
            request.app.state.db, lambda conn: authenticate(conn, token)
        )
        if token
        else None
    )
    if user is None:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"rejected": True},
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


@router.post("/ui/theme")
async def set_theme(request: Request) -> Response:
    """Remember a light/dark choice, and come back to the page it was made on.

    A form rather than a script: the server writes the `<html>` tag, so the
    server is what has to know, and a toggle that needs JavaScript would be
    the one control on this dashboard that does.
    """
    fields = await _fields(request)
    picked = fields.get("theme", "")
    back = fields.get("back", "/ui")
    answer = RedirectResponse(
        back if back.startswith("/ui") else "/ui", status_code=303
    )
    if picked in ("light", "dark"):
        answer.set_cookie(
            THEME_COOKIE,
            picked,
            max_age=60 * 60 * 24 * 365,
            httponly=False,  # it decides a colour, not an identity
            samesite="lax",
        )
    else:
        answer.delete_cookie(THEME_COOKIE)
    return answer


# The mark the page head carries as a data URI, for whatever asks for the
# conventional path: a browser on a response with no head, such as a 404.
FAVICON = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>"
    "<path d='M8 5v2.4M8 7.6L4.2 10M8 7.6l3.8 2.4' stroke='#B4552D' "
    "stroke-width='1.1' fill='none'/>"
    "<circle cx='8' cy='3' r='2.2' fill='#B4552D'/>"
    "<circle cx='3.6' cy='12' r='2.2' fill='#B4552D' opacity='.65'/>"
    "<circle cx='12.4' cy='12' r='2.2' fill='#B4552D' opacity='.65'/>"
    "</svg>"
)


@router.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(
        FAVICON,
        media_type="image/svg+xml",
        headers={"cache-control": "max-age=86400"},
    )


@router.post("/ui/lang")
async def set_lang(request: Request) -> Response:
    """Remember the reader's language, and come back to the same page.

    A form and a cookie, like the theme, so the server writes the page in
    that language from the first byte and no script is needed to switch.
    """
    fields = await _fields(request)
    picked = fields.get("lang", "")
    back = fields.get("back", "/ui")
    answer = RedirectResponse(
        back if back.startswith("/ui") else "/ui", status_code=303
    )
    if picked in i18n.LANGS and picked != i18n.DEFAULT:
        answer.set_cookie(
            i18n.COOKIE,
            picked,
            max_age=60 * 60 * 24 * 365,
            httponly=False,  # it decides the wording, not an identity
            samesite="lax",
        )
    else:
        answer.delete_cookie(i18n.COOKIE)
    return answer
