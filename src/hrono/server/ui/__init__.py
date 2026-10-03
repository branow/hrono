"""The dashboard shell: server-rendered, logged in, role-gated (T49, #180).

Jinja and plain HTML, served by the same process that owns the database — so
the dashboard ships inside the one `hrono` binary with no build step and no
second release artifact. The stakeholder chose that on 2026-09-27.

Authentication is the API's, not a second system: the browser carries the SAME
token the CLI uses, in an HttpOnly SameSite=Strict cookie, resolved by the same
``require_role`` dependency every API route uses. What differs is only the
FAILURE — an API caller gets a 401, a browser gets the login page, because a
401 in a tab is a dead end.

One router, one module per subject (#195). Importing the view modules at the
bottom is what registers their routes on it, so `app.py` still imports one
name; it is at the bottom because they import this module back for the router
and the shared dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from hrono.auth.users import User
from hrono.errors import AppError
from hrono.registry import store as registry_store
from hrono.server import prose
from hrono.server.auth import allows, require_role

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent / "templates")
)
# Model-written text is markdown; `prose.markdown` renders it with HTML
# escaped, so the filter's output is safe to mark safe (`server/prose.py`).
templates.env.filters["markdown"] = prose.markdown

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
# The API's edit routes are admin-gated (`server/edits.py`). A page that
# accepted a writer for the same operation would be a second, weaker
# authorization for it — the thing #180 refused, said as a role.
Admin = Annotated[User, Depends(_viewer("admin"))]


def _back(tree: str, node_id: int, **outcome: str) -> Response:
    """Redirect-after-POST to the topic, carrying what happened."""
    query = urlencode({"tree": tree, **{k: v for k, v in outcome.items() if v}})
    return RedirectResponse(
        f"/ui/trees/{tree}/nodes/{node_id}?{query}", status_code=303
    )


THEMES = ("system", "light", "dark")
THEME_COOKIE = "hrono_theme"


def chosen_theme(request: Request) -> str:
    """The theme this browser asked for, or "" for whatever the OS says.

    A cookie rather than localStorage: the page is rendered on the server, so
    the server has to know before it writes the `<html>` tag — and doing it
    here means the choice survives with JavaScript switched off, which is the
    rule the rest of this dashboard is built to.
    """
    picked = request.cookies.get(THEME_COOKIE, "")
    return picked if picked in ("light", "dark") else ""


def next_theme(current: str) -> str:
    """system -> light -> dark -> system, so every state is reachable."""
    order = {"": "light", "light": "dark", "dark": ""}
    return order.get(current, "light")


def switch(here: str, tree: str, to: str) -> str:
    """The same page, in another tree.

    Switching trees used to bounce you to the overview whatever you were
    looking at. Every view except one is the same question asked of a
    different tree, so it should stay put — the exception is a page about ONE
    topic, because a topic id does not exist in another tree, and that falls
    back to the new tree's map rather than to a 404.
    """
    if "/nodes/" in here:
        return f"/ui/trees/{to}/graph?tree={to}"
    rebased = here.replace(f"/trees/{tree}/", f"/trees/{to}/", 1)
    return f"{rebased}?tree={to}"


# One row per page a person can navigate to: its key, its label, where it
# lives, and the paths that are "inside" it. A run's page belongs to Runs, a
# topic's page to no tab at all, so it gets a transient one of its own rather
# than lighting up Map for a page that is not the map. Data, so the nav and the
# current-page mark cannot disagree about which pages exist (#215).
TABS: tuple[tuple[str, str, str, str], ...] = (
    ("home", "Home", "/ui", r"/ui"),
    ("map", "Map", "/ui/trees/{tree}/graph", r"/ui/trees/[^/]+/graph"),
    ("ask", "Ask", "/ui/trees/{tree}/ask", r"/ui/trees/[^/]+/ask"),
    (
        "runs",
        "Runs",
        "/ui/jobs",
        r"/ui/jobs(/.*)?|/ui/trees/[^/]+/activity",
    ),
    (
        "health",
        "Health",
        "/ui/trees/{tree}/triage",
        r"/ui/trees/[^/]+/triage",
    ),
    ("export", "Export", "/ui/trees/{tree}/export", r"/ui/trees/[^/]+/export"),
    ("settings", "Settings", "/ui/config", r"/ui/config(/.*)?"),
    ("guide", "Guide", "/ui/guide", r"/ui/guide"),
)
TOPIC_PAGE = r"/ui/trees/[^/]+/nodes/\d+"


# Drawn for an admin only, from the same rule that refuses everyone else the
# page (#209), and placed before the Guide.
ACCESS_TAB = ("access", "Access", "/ui/access", r"/ui/access(/.*)?")


def tabs(here: str, tree: str, role: str = "reader") -> list[dict[str, object]]:
    """The navigation: every tab, the current one marked, and a topic's own."""
    path = here.rstrip("/") or "/ui"
    shown = list(TABS)
    if allows(role, "admin"):
        shown.insert(-1, ACCESS_TAB)
    rows = [
        {
            "label": label,
            "href": f"{href.format(tree=tree)}?tree={tree}",
            "current": re.fullmatch(inside, path) is not None,
        }
        for _, label, href, inside in shown
    ]
    if re.fullmatch(TOPIC_PAGE, path):
        rows.insert(
            2,
            {"label": "Topic", "href": here + f"?tree={tree}", "current": True},
        )
    return rows


# The tree switcher rewrites the current path per tree, which is routing, not
# markup — so it is a function the template calls rather than a chain of Jinja
# string operations.
templates.env.globals["switch"] = switch
templates.env.globals["tabs"] = tabs
# Read from the request in the template rather than threaded through a dozen
# route context dicts: the theme is chrome, and every page has the same answer.
templates.env.globals["chosen_theme"] = chosen_theme
templates.env.globals["next_theme"] = next_theme


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


# Registering the routes: each of these imports this module for `router` and
# the role dependencies, so they are imported last and only for that effect.
from hrono.server.ui import (  # noqa: E402, F401
    access,
    ask,
    export,
    guide,
    jobs,
    nodes,
    overview,
    session,
    settings,
    views,
)
