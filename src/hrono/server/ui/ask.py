"""The Ask page: what recall hands an agent, for any question.

Recall is one of hrono's two doors, and this page opens it outside a terminal.
The page asks exactly what ``POST /trees/{name}/recall`` asks — the
same ``recall.ask`` — and shows each passage as an agent receives it, with the
file and byte range it came from, its fused score, and the topic that holds it.

Recall REFUSES when nothing clears its confidence floor, by design: a guess
injected into an agent's context is worse than none. So a refusal is shown as a
result, with the tree's top topics as the place to look instead, never as an
error.

The question lives in the URL (a GET, since asking changes nothing), so an
answer can be shared; the last few questions this browser asked are kept in a
cookie for comparing before and after a fix. The cookie keeps a compact
snapshot of what each answered, so asking one again marks every passage new,
moved or the same, and lists the ones that dropped out. A missing or
still-loading embedding backend is a message with a next step, not a 503.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from urllib.parse import unquote, urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from hrono.embed.runner import EmbedError
from hrono.errors import Unavailable
from hrono.naming import name, names
from hrono.recall.ask import ask
from hrono.recall.engine import Hit
from hrono.server.i18n import gettext as _
from hrono.server.ui import Reader, _trees, ask_history, router, templates

HISTORY_COOKIE = "hrono_asked"
HISTORY = ask_history.HISTORY
LIMIT = 10


@router.get("/ui/trees/{tree}/ask", response_class=HTMLResponse)
def ask_page(
    request: Request, user: Reader, tree: str, q: str = ""
) -> Response:
    """Ask ``q`` of ``tree``; show the passages, the refusal, or what to fix."""
    question = q.strip()
    asked = ask_history.read(request.cookies.get(HISTORY_COOKIE, ""))
    outcome = _answer(request, tree, question) if question else Answer()
    past = ask_history.before(asked, question) if question else None
    change = (
        ask_history.compare(past, outcome.hits)
        if past is not None and outcome.problem is None
        else None
    )
    if question:
        kept = None if outcome.problem else ask_history.snapshot(outcome.hits)
        asked = ask_history.remember(asked, question, kept)
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        hits = [_shown(conn, tree, hit) for hit in outcome.hits]
        for index, shown in enumerate(hits):
            shown["status"] = change.status[index] if change else None
            shown["status_label"] = (
                _status(change.status[index]) if change else None
            )
        explore = _explore(conn, tree) if outcome.refused else []
    page = templates.TemplateResponse(
        request,
        "ask.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "question": question,
            "hits": hits,
            "refused": outcome.refused,
            "problem": outcome.problem,
            "loading": outcome.loading,
            "explore": explore,
            "change": change,
            "asked": [(a.question, ask_link(tree, a.question)) for a in asked],
        },
    )
    if question:
        page.set_cookie(
            HISTORY_COOKIE,
            ask_history.write(asked),
            max_age=60 * 60 * 24,
            httponly=True,
            samesite="lax",
        )
    return page


@dataclass(frozen=True)
class Answer:
    """One of: passages, a refusal, or a reason recall could not run."""

    hits: tuple[Hit, ...] = ()
    refused: str | None = None
    problem: str | None = None
    loading: bool = False


def _answer(request: Request, tree: str, question: str) -> Answer:
    try:
        result = ask(request.app.state.db, tree, question, LIMIT)
    except Unavailable as exc:
        return Answer(problem=exc.message, loading=True)
    except EmbedError as exc:
        return Answer(problem=str(exc))
    if not result.hits:
        return Answer(refused=result.message)
    return Answer(hits=result.hits)


def _shown(conn: sqlite3.Connection, tree: str, hit: Hit) -> dict[str, object]:
    path, _at, version = hit.uri.rpartition("@")
    return {
        "kind": _("brief") if hit.kind == "summary" else _("source"),
        "path": path,
        "version": version[:12],
        "where": unquote(hit.header.removeprefix(hit.uri).strip()),
        "start": hit.start,
        "end": hit.end,
        "score": hit.score,
        "body": hit.body,
        "topic": None
        if hit.topic is None
        else {
            "title": name(conn, hit.topic),
            "link": f"/ui/trees/{tree}/nodes/{hit.topic}?tree={tree}",
        },
    }


def _status(status: str) -> str:
    """A passage's mark against the last answer, in the page's language."""
    moved = status.removeprefix("moved from #")
    if moved != status:
        return _("moved from #{rank}", rank=moved)
    marks = {"new": _("new"), "same": _("same"), "changed": _("changed")}
    return marks.get(status, status)


def _explore(conn: sqlite3.Connection, tree: str) -> list[dict[str, str]]:
    """The topics just under the root: where a person starts looking."""
    rows = conn.execute(
        "SELECT c.child_id AS id FROM node_children c "
        "JOIN nodes p ON p.id = c.parent_id "
        "WHERE p.tree = ? AND p.level = "
        "(SELECT MAX(level) FROM nodes WHERE tree = ?) ORDER BY c.child_id",
        (tree, tree),
    ).fetchall()
    called = names(conn, [int(row["id"]) for row in rows])
    return [
        {
            "title": called[int(row["id"])],
            "link": f"/ui/trees/{tree}/nodes/{row['id']}?tree={tree}",
        }
        for row in rows
    ]


def ask_link(tree: str, question: str) -> str:
    """The Ask page address that asks ``question`` of ``tree``."""
    return f"/ui/trees/{tree}/ask?{urlencode({'tree': tree, 'q': question})}"
