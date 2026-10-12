"""The dashboard shell: server-rendered, logged in, role-gated.

Jinja and plain HTML, served by the same process that owns the database — so
the dashboard ships inside the one `hrono` binary with no build step and no
second release artifact.

Authentication is the API's, not a second system: the browser carries the SAME
token the CLI uses, in an HttpOnly SameSite=Strict cookie, resolved by the same
``require_role`` dependency every API route uses. What differs is only the
FAILURE — an API caller gets a 401, a browser gets the login page, because a
401 in a tab is a dead end.

One router, one module per subject. Importing the view modules at the bottom is
what registers their routes on it, so `app.py` still imports one name; it is at
the bottom because they import this module back for the router and the shared
dependencies.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qs, urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from starlette.concurrency import run_in_threadpool

from hrono.auth.users import User
from hrono.errors import AppError
from hrono.ingest.split.constants import PASSAGE_BYTES, SECTION_BYTES
from hrono.jobs.aggregate import PARTIAL
from hrono.registry import store as registry_store
from hrono.server import prose
from hrono.server.auth import allows, require_role
from hrono.server.words import compact, counted, size, weight

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).parent.parent / "templates")
)
# Model-written text is markdown; `prose.markdown` renders it with HTML
# escaped, so the filter's output is safe to mark safe (`server/prose.py`).
templates.env.filters["markdown"] = prose.markdown


def status_word(status: str) -> str:
    """A run's status as a reader should see it.

    `partial` is the parent-only status for a run with some stages done and
    the rest still going (`jobs/aggregate.py`). To a person it reads as
    "finished incompletely", so the page says `running` and the n/m beside it
    says how far. The API and the CLI keep the derived word.
    """
    return "running" if status == PARTIAL else status


templates.env.filters["status_word"] = status_word


def idents(text: str) -> Markup:
    """Text with `backticked` identifiers set as `<code>`, the rest escaped.

    A refusal has to name an identifier a person types (a name prefix) that
    is not a glossary word; `<code>` is where the page keeps those.
    """
    parts = str(escape(text)).split("`")
    if len(parts) % 2 == 0:  # an unpaired backtick is just text
        return Markup(escape(text))
    return Markup(
        "".join(
            f"<code>{part}</code>" if index % 2 else part
            for index, part in enumerate(parts)
            if part
        )
    )


templates.env.filters["idents"] = idents
templates.env.globals["partial_status"] = PARTIAL
templates.env.filters["counted"] = counted
templates.env.filters["size"] = size
templates.env.filters["weight"] = weight
templates.env.filters["compact"] = compact
templates.env.filters["fromjson"] = json.loads
# the two leaf budgets, quoted on several pages: one source for the number
templates.env.globals["limits"] = {
    "section": SECTION_BYTES,
    "passage": PASSAGE_BYTES,
}

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


async def write_off_loop(database, fn):  # noqa: ANN001, ANN201
    """One write block in the threadpool, not on the event loop.

    A write can wait the whole busy timeout (seconds) while a build holds the
    lock, and a handler doing that on the loop stalls every request, page and
    SSE stream of the process. ``setup.py`` already offloaded its slow calls;
    the other pages did not, which made the discipline accidental. ``fn`` runs
    with the open write connection and its return value comes back.
    """

    def work():  # noqa: ANN202
        with database.write() as conn:
            return fn(conn)

    return await run_in_threadpool(work)


async def read_off_loop(database, fn):  # noqa: ANN001, ANN201
    """One read block in the threadpool — ``write_off_loop``'s read twin."""

    def work():  # noqa: ANN202
        with database.connect() as conn:
            return fn(conn)

    return await run_in_threadpool(work)


class LoginRequired(AppError):
    """A browser reached a page without a usable cookie.

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
# authorization for it.
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

    Switching trees keeps you on the page you were looking at. Every view
    except one is the same question asked of a different tree, so it should
    stay put — the exception is a page about ONE
    topic, because a topic id does not exist in another tree, and that falls
    back to the new tree's map rather than to a 404.
    """
    if "/nodes/" in here:
        return f"/ui/trees/{to}/graph?tree={to}"
    rebased = here.replace(f"/trees/{tree}/", f"/trees/{to}/", 1)
    return f"{rebased}?tree={to}"


# The menu: seven sections, each owning the pages inside it. A section with
# more than one page shows them as sub-tabs under the bar, so a page is never
# more than two clicks away and the bar never grows a tab per page. Data, so
# the bar, the sub-tabs and the current-page mark cannot disagree.
# (key, label, href, inside, admin only)
Page = tuple[str, str, str, str, bool]
SECTIONS: tuple[tuple[str, str, tuple[Page, ...]], ...] = (
    ("home", "Home", (("home", "Overview", "/ui", r"/ui", False),)),
    (
        "map",
        "Map",
        (
            (
                "map",
                "Map",
                "/ui/trees/{tree}/graph",
                r"/ui/trees/[^/]+/graph",
                False,
            ),
            (
                "search",
                "Search",
                "/ui/trees/{tree}/find",
                r"/ui/trees/[^/]+/(find|files)",
                False,
            ),
            (
                "outline",
                "Outline",
                "/ui/trees/{tree}/outline",
                r"/ui/trees/[^/]+/outline",
                False,
            ),
        ),
    ),
    (
        "ask",
        "Ask",
        (
            (
                "ask",
                "Recall",
                "/ui/trees/{tree}/ask",
                r"/ui/trees/[^/]+/ask",
                False,
            ),
            (
                "demo",
                "Agent demo",
                "/ui/trees/{tree}/demo",
                r"/ui/trees/[^/]+/demo",
                False,
            ),
        ),
    ),
    (
        "runs",
        "Runs",
        (
            ("runs", "Runs", "/ui/jobs", r"/ui/jobs(/.*)?", False),
            (
                "changes",
                "Changes",
                "/ui/trees/{tree}/activity",
                r"/ui/trees/[^/]+/activity",
                False,
            ),
            ("usage", "Usage", "/ui/usage", r"/ui/usage", False),
        ),
    ),
    (
        "health",
        "Health",
        (
            (
                "health",
                "Health",
                "/ui/trees/{tree}/triage",
                r"/ui/trees/[^/]+/triage",
                False,
            ),
        ),
    ),
    (
        "export",
        "Export",
        (
            (
                "export",
                "Export",
                "/ui/trees/{tree}/export",
                r"/ui/trees/[^/]+/export",
                False,
            ),
        ),
    ),
    (
        "settings",
        "Settings",
        (
            (
                "settings",
                "Settings",
                "/ui/config",
                r"/ui/(config(/.*)?|setup)",
                False,
            ),
            ("access", "Access", "/ui/access", r"/ui/access(/.*)?", True),
        ),
    ),
)
TOPIC_PAGE = r"/ui/trees/[^/]+/nodes/\d+"


def _visible(pages: tuple[Page, ...], role: str) -> list[Page]:
    return [page for page in pages if not page[4] or allows(role, "admin")]


def _link(href: str, tree: str) -> str:
    return f"{href.format(tree=tree)}?tree={tree}"


def tabs(here: str, tree: str, role: str = "reader") -> list[dict[str, object]]:
    """The bar: a tab per section, its first page the target, the current
    section marked; a topic's page gets a transient tab of its own."""
    path = here.rstrip("/") or "/ui"
    rows = []
    for _, label, pages in SECTIONS:
        shown = _visible(pages, role)
        rows.append(
            {
                "label": label,
                "href": _link(shown[0][2], tree),
                "current": any(re.fullmatch(page[3], path) for page in shown),
            }
        )
    if re.fullmatch(TOPIC_PAGE, path):
        rows.insert(
            2,
            {"label": "Topic", "href": here + f"?tree={tree}", "current": True},
        )
    return rows


def subtabs(
    here: str, tree: str, role: str = "reader"
) -> list[dict[str, object]]:
    """The pages of the current section, when it has more than one."""
    path = here.rstrip("/") or "/ui"
    for _, _, pages in SECTIONS:
        shown = _visible(pages, role)
        if len(shown) > 1 and any(re.fullmatch(p[3], path) for p in shown):
            return [
                {
                    "label": label,
                    "href": _link(href, tree),
                    "current": re.fullmatch(inside, path) is not None,
                }
                for _, label, href, inside, _ in shown
            ]
    return []


# The tree switcher rewrites the current path per tree, which is routing, not
# markup — so it is a function the template calls rather than a chain of Jinja
# string operations.
templates.env.globals["switch"] = switch
templates.env.globals["tabs"] = tabs
templates.env.globals["subtabs"] = subtabs
# Read from the request in the template rather than threaded through a dozen
# route context dicts: the theme is chrome, and every page has the same answer.
templates.env.globals["chosen_theme"] = chosen_theme
templates.env.globals["next_theme"] = next_theme


def _trees(conn: object) -> list[str]:
    """Every declared tree, or `default` when none are.

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
    demo,
    export,
    find,
    guide,
    health,
    jobs,
    nodes,
    overview,
    session,
    settings,
    setup,
    usage,
    views,
)
