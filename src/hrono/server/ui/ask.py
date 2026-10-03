"""The Ask page (#207): what recall hands an agent, for any question.

Recall is one of hrono's two doors, and until this page it opened only from a
terminal. The page asks exactly what ``POST /trees/{name}/recall`` asks — the
same ``recall.ask`` — and shows each passage as an agent receives it, with the
file and byte range it came from, its fused score, and the topic that holds it.

Recall REFUSES when nothing clears its confidence floor, by design: a guess
injected into an agent's context is worse than none. So a refusal is shown as a
result, with the tree's top topics as the place to look instead, never as an
error.

The question lives in the URL (a GET, since asking changes nothing), so an
answer can be shared; the last few questions this browser asked are kept in a
cookie for comparing before and after a fix. A missing or still-loading
embedding backend is a message with a next step, not a 503.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from urllib.parse import quote, unquote, urlencode

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from hrono.embed.runner import EmbedError
from hrono.errors import Unavailable
from hrono.export.render import heading
from hrono.recall.ask import ask
from hrono.recall.engine import Hit
from hrono.server.ui import Reader, _trees, router, templates

HISTORY_COOKIE = "hrono_asked"
HISTORY = 6
LIMIT = 10


@router.get("/ui/trees/{tree}/ask", response_class=HTMLResponse)
def ask_page(
    request: Request, user: Reader, tree: str, q: str = ""
) -> Response:
    """Ask ``q`` of ``tree``; show the passages, the refusal, or what to fix."""
    question = q.strip()
    asked = _history(request)
    outcome = _answer(request, tree, question) if question else Answer()
    if question:
        asked = [question, *[a for a in asked if a != question]][:HISTORY]
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        hits = [_shown(conn, tree, hit) for hit in outcome.hits]
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
            "asked": [(a, _link(tree, a)) for a in asked],
        },
    )
    if question:
        page.set_cookie(
            HISTORY_COOKIE,
            quote(json.dumps(asked)),
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
    path, _, version = hit.uri.rpartition("@")
    return {
        "kind": "brief" if hit.kind == "summary" else "source",
        "path": path,
        "version": version[:12],
        "where": hit.header.removeprefix(hit.uri).strip(),
        "start": hit.start,
        "end": hit.end,
        "score": hit.score,
        "body": hit.body,
        "topic": None
        if hit.topic is None
        else {
            "title": heading(conn, hit.topic),
            "link": f"/ui/trees/{tree}/nodes/{hit.topic}?tree={tree}",
        },
    }


def _explore(conn: sqlite3.Connection, tree: str) -> list[dict[str, str]]:
    """The topics just under the root: where a person starts looking."""
    rows = conn.execute(
        "SELECT c.child_id AS id FROM node_children c "
        "JOIN nodes p ON p.id = c.parent_id "
        "WHERE p.tree = ? AND p.level = "
        "(SELECT MAX(level) FROM nodes WHERE tree = ?) ORDER BY c.child_id",
        (tree, tree),
    ).fetchall()
    return [
        {
            "title": heading(conn, int(row["id"])),
            "link": f"/ui/trees/{tree}/nodes/{row['id']}?tree={tree}",
        }
        for row in rows
    ]


def _history(request: Request) -> list[str]:
    try:
        stored = json.loads(unquote(request.cookies.get(HISTORY_COOKIE, "[]")))
    except ValueError:
        return []
    if not isinstance(stored, list):
        return []
    return [str(item) for item in stored][:HISTORY]


def _link(tree: str, question: str) -> str:
    return f"/ui/trees/{tree}/ask?{urlencode({'tree': tree, 'q': question})}"
