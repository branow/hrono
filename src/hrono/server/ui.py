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

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qs, quote, urlencode

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ValidationError

from hrono import edits, notes, pins
from hrono.auth.users import User, authenticate
from hrono.db import update_log
from hrono.embed.model import resolve_embedding_model
from hrono.errors import AppError, DomainError, NotFound
from hrono.jobs import store as job_store
from hrono.jobs.aggregate import rollup, total_spend
from hrono.jobs.cancel import cancel
from hrono.jobs.model import to_job
from hrono.jobs.worker import enqueue
from hrono.registry import store as registry_store
from hrono.server import config_view, graph, overlays, triage
from hrono.server.auth import COOKIE, require_role
from hrono.server.edits import BriefText, NoteText, Rename
from hrono.summarize import briefs

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
# The API's edit routes are admin-gated (`server/edits.py`). A page that
# accepted a writer for the same operation would be a second, weaker
# authorization for it — the thing #180 refused, said as a role.
Admin = Annotated[User, Depends(_viewer("admin"))]


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

# Enough to recognise a chunk, not enough to lose the topic off the screen. A
# section is ~10 KB and a topic can hold thirty of them (#182).
PREVIEW_CHARS = 600


@router.get("/ui/config", response_class=HTMLResponse)
def config_page(request: Request, user: Reader, tree: str = "") -> Response:
    """Every registry collection, with secrets masked.

    Masked through the registry's OWN `mask()`, not a second redaction here: it
    reads each collection's declared `secret_paths` (#142), so a source type
    whose credential moves is masked by declaring the new path — and there is
    no second place that can forget to.
    """
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        collections = config_view.tables(conn)
    return templates.TemplateResponse(
        request,
        "config.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree if tree in trees else trees[0],
            "collections": collections,
            "can_write": user.role in {"writer", "admin"},
        },
    )


@router.get("/ui/trees/{tree}/activity", response_class=HTMLResponse)
def activity_page(tree: str, request: Request, user: Reader) -> Response:
    """What the tree DECIDED — the only record of its own judgement.

    A stale brief is a fact; "judged, not materially changed, did not climb" is
    a decision, and an operator who disagrees with the map needs to read the
    decision rather than infer it from the shape.
    """
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        rows, total = update_log.recent(conn, tree)
    return templates.TemplateResponse(
        request,
        "activity.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "rows": [_decision(row) for row in rows],
            "total": total,
            "can_write": user.role in {"writer", "admin"},
        },
    )


def _decision(row: object) -> dict[str, object]:
    """One logged decision, with the abstention called out.

    #105 made abstaining a first-class outcome and #132 made it visible in a
    job's result, because a topic that CHANGED and was not judged leaves a
    stale brief in service. On this page that is the row to look at.
    """
    action = str(row["action"])  # type: ignore[index]
    return {
        "node_id": int(row["node_id"]),  # type: ignore[index]
        "verdict": str(row["verdict"]),  # type: ignore[index]
        "action": action,
        "climbed_to": row["climbed_to"],  # type: ignore[index]
        "when": str(row["created_at"])[:19].replace("T", " "),  # type: ignore[index]
        # the ACTION carries it, not the verdict: `_record` writes the verdict
        # as "unparseable" and the action as "abstained" (propagate.py)
        "abstained": action == "abstained",
    }


@router.get("/ui/trees/{tree}/triage", response_class=HTMLResponse)
def triage_page(tree: str, request: Request, user: Reader) -> Response:
    """What is wrong with this tree, counted, each linking to where it is."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        items = triage.survey(conn, tree)
    return templates.TemplateResponse(
        request,
        "triage.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "items": items,
            "clean": triage.clean(items),
            "can_write": user.role in {"writer", "admin"},
        },
    )


@router.get("/ui/trees/{tree}/graph", response_class=HTMLResponse)
def graph_page(
    tree: str,
    request: Request,
    user: Reader,
    open: str = "",
    edges: str = "",
) -> Response:
    """The tree, drawn — and every view of it is a URL.

    The expand state rides in `open` rather than in the page, so a graph
    someone is looking at can be pasted to someone else. It is also why this
    needs no JavaScript: toggling is a link.
    """
    opened = _opened(open)
    kinds = overlays.parse(edges)
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        drawn = graph.build(conn, tree, sorted(opened))
        overlay = overlays.build(
            conn, tree, [node.id for node in drawn.nodes], kinds
        )
    return templates.TemplateResponse(
        request,
        "graph.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "graph": {
                "nodes": [
                    _with_toggle(node, tree, opened) for node in drawn.nodes
                ],
                "edges": drawn.edges,
                "width": drawn.width,
                "height": drawn.height,
            },
            "overlay": {
                "links": _drawn_links(overlay, drawn),
                "unavailable": overlay.unavailable,
                "toggles": _edge_toggles(tree, open, kinds),
            },
            "can_write": user.role in {"writer", "admin"},
        },
    )


def _drawn_links(
    overlay: overlays.Overlay, drawn: graph.Graph
) -> list[dict[str, object]]:
    """Give each link the coordinates of the topics it joins.

    A link whose end is not on the page is dropped rather than drawn to
    nowhere: the overlay describes what is DRAWN, and `?open=` decides that.
    """
    placed = {node.id: (node.x, node.y) for node in drawn.nodes}
    return [
        {
            "kind": link.kind,
            "label": link.label,
            "x1": placed[link.source][0],
            "y1": placed[link.source][1],
            "x2": placed[link.target][0],
            "y2": placed[link.target][1],
        }
        for link in overlay.links
        if link.source in placed and link.target in placed
    ]


def _edge_toggles(
    tree: str, open: str, kinds: Sequence[str]
) -> list[dict[str, object]]:
    """One on/off link per overlay, keeping the expand state.

    The overlay is part of the URL for the same reason the expand state is: a
    graph someone is looking at can be pasted to someone else.
    """
    toggles = []
    for kind in overlays.KINDS:
        rest = (
            [k for k in kinds if k != kind]
            if kind in kinds
            else [
                *kinds,
                kind,
            ]
        )
        query = urlencode(
            {
                k: v
                for k, v in (
                    ("tree", tree),
                    ("open", open),
                    ("edges", ",".join(rest)),
                )
                if v
            },
            quote_via=quote,
            safe=",",
        )
        toggles.append(
            {
                "kind": kind,
                "on": kind in kinds,
                "href": f"/ui/trees/{tree}/graph?{query}",
            }
        )
    return toggles


def _opened(raw: str) -> set[int]:
    """The ids in `?open=`, ignoring anything that is not one.

    A hand-edited or truncated URL should draw a smaller graph, never a 500 —
    this parameter is a view, and a view cannot be invalid.
    """
    out: set[int] = set()
    for part in raw.split(","):
        if part.strip().isdigit():
            out.add(int(part))
    return out


def _with_toggle(
    node: object, tree: str, opened: set[int]
) -> dict[str, object]:
    """Each node carries the URL that opens or closes it."""
    node_id = node.id  # type: ignore[attr-defined]
    after = opened - {node_id} if node_id in opened else opened | {node_id}
    query = ",".join(str(value) for value in sorted(after))
    return {
        "id": node_id,
        "title": node.title,  # type: ignore[attr-defined]
        "holds": node.holds,  # type: ignore[attr-defined]
        "stale": node.stale,  # type: ignore[attr-defined]
        "has_hidden_children": node.has_hidden_children,  # type: ignore[attr-defined]
        "x": node.x,  # type: ignore[attr-defined]
        "y": node.y,  # type: ignore[attr-defined]
        "radius": round(node.radius, 1),  # type: ignore[attr-defined]
        "toggle": f"/ui/trees/{tree}/graph?tree={tree}&open={query}",
    }


@router.get("/ui/trees/{tree}/nodes/{node_id}", response_class=HTMLResponse)
def node_page(
    tree: str,
    node_id: int,
    request: Request,
    user: Reader,
    error: str = "",
    done: str = "",
) -> Response:
    """One topic: what it says, where it sits, and what it is made of.

    `error` and `done` carry the result of a write back through the redirect,
    so the page a write lands on is a URL like any other and a refresh repeats
    nothing.
    """
    with request.app.state.db.connect() as conn:
        if not edits.node_exists(conn, tree, node_id):
            raise NotFound(f"node not found in tree {tree}: {node_id}")
        node = _node(conn, tree, node_id)
        candidates = _candidates(conn, tree, node_id, int(node["level"]))  # type: ignore[arg-type]
        trees = _trees(conn)
    return templates.TemplateResponse(
        request,
        "node.html",
        {
            "user": user,
            "trees": trees,
            "tree": tree,
            "node": node,
            "candidates": candidates,
            "error": error,
            "done": done,
            "can_write": user.role in {"writer", "admin"},
            "can_edit": user.role == "admin",
        },
    )


def _back(tree: str, node_id: int, **outcome: str) -> Response:
    """Redirect-after-POST to the topic, carrying what happened."""
    query = urlencode({"tree": tree, **{k: v for k, v in outcome.items() if v}})
    return RedirectResponse(
        f"/ui/trees/{tree}/nodes/{node_id}?{query}", status_code=303
    )


async def _edit(
    request: Request,
    model: type[BaseModel],
) -> tuple[BaseModel | None, str]:
    """Read a form through the API's OWN validation model.

    "A title may not be blank" is one rule, in `server/edits.py`, not a second
    one written here that could drift from it.
    """
    fields = await _fields(request)
    try:
        return model(**fields), ""
    except ValidationError as exc:
        return None, _first_problem(exc)


def _first_problem(exc: ValidationError) -> str:
    problem = exc.errors()[0]
    field = ".".join(str(part) for part in problem["loc"]) or "input"
    return f"{field}: {problem['msg']}"


@router.post("/ui/trees/{tree}/nodes/{node_id}/rename")
async def rename_from_the_page(
    tree: str, node_id: int, request: Request, user: Admin
) -> Response:
    """Name a topic by hand; `edits.rename` pins the brief so it sticks."""
    body, problem = await _edit(request, Rename)
    if body is None:
        return _back(tree, node_id, error=problem)
    with request.app.state.db.write() as conn:
        edits.rename(conn, tree, node_id, body.title)  # type: ignore[attr-defined]
    return _back(tree, node_id, done="renamed")


@router.post("/ui/trees/{tree}/nodes/{node_id}/brief")
async def brief_from_the_page(
    tree: str, node_id: int, request: Request, user: Admin
) -> Response:
    """Write the brief by hand — through the path that also feeds recall."""
    body, problem = await _edit(request, BriefText)
    if body is None:
        return _back(tree, node_id, error=problem)
    with request.app.state.db.write() as conn:
        edits.override_brief(conn, tree, node_id, body.text)  # type: ignore[attr-defined]
    return _back(tree, node_id, done="brief written")


@router.post("/ui/trees/{tree}/nodes/{node_id}/note")
async def note_from_the_page(
    tree: str, node_id: int, request: Request, user: Admin
) -> Response:
    """Annotate a topic; the export shows it to the traversing agent."""
    body, problem = await _edit(request, NoteText)
    if body is None:
        return _back(tree, node_id, error=problem)
    with request.app.state.db.write() as conn:
        edits.require_node(conn, tree, node_id)
        notes.add(conn, notes.NODE, node_id, body.text)  # type: ignore[attr-defined]
    return _back(tree, node_id, done="note added")


def _candidates(conn: object, tree: str, node_id: int, level: int) -> dict:
    """The topics an operator may pick, so nobody has to type an id.

    A parent sits exactly one level up and a merge partner at the same level
    (`edits.reparent`, `edits.require_one_level`). Offering anything else
    teaches the rule through a refusal, which is the worse way to learn it.
    """

    def at(wanted: int) -> list[dict[str, object]]:
        return [
            {
                "id": int(row["id"]),
                "title": row["title"] or f"topic {row['id']}",
            }
            for row in conn.execute(  # type: ignore[attr-defined]
                "SELECT id, title FROM nodes WHERE tree = ? AND level = ? "
                "AND id != ? ORDER BY id",
                (tree, wanted, node_id),
            ).fetchall()
        ]

    return {"parents": at(level + 1), "siblings": at(level)}


def _confirmed(fields: dict[str, str]) -> bool:
    """A destructive form has to be ticked.

    No JS on this dashboard, so no `confirm()`. A checkbox is the same promise
    and it still works with scripting off — and it is refused HERE, not hidden
    in the markup, so a hand-made POST is refused too.
    """
    return fields.get("confirm", "") != ""


@router.post("/ui/trees/{tree}/nodes/{node_id}/reparent")
async def reparent_from_the_page(
    tree: str, node_id: int, request: Request, user: Admin
) -> Response:
    """Hang a topic under a chosen parent; `edits.reparent` pins it there."""
    fields = await _fields(request)
    parent = fields.get("to", "")
    if not parent.isdigit():
        return _back(tree, node_id, error="choose a parent")
    try:
        with request.app.state.db.write() as conn:
            edits.reparent(conn, tree, node_id, int(parent))
    except AppError as exc:
        return _back(tree, node_id, error=str(exc))
    return _back(tree, node_id, done=f"moved under topic {parent}")


@router.post("/ui/trees/{tree}/nodes/{node_id}/merge")
async def merge_from_the_page(
    tree: str, node_id: int, request: Request, user: Admin
) -> Response:
    """Fold two topics into one and land on the survivor.

    The topic the operator was looking at may be the one that goes, so where
    they end up is computed rather than assumed: `edits.merge` returns the
    survivor, and the lowest id wins (#158).
    """
    fields = await _fields(request)
    partner = fields.get("with", "")
    if not partner.isdigit():
        return _back(tree, node_id, error="choose a topic to merge with")
    if not _confirmed(fields):
        return _back(tree, node_id, error="tick the box to confirm a merge")
    try:
        with request.app.state.db.write() as conn:
            survivor = edits.merge(conn, tree, [node_id, int(partner)])
    except AppError as exc:
        return _back(tree, node_id, error=str(exc))
    return _back(tree, survivor, done=f"merged with topic {partner}")


@router.post("/ui/trees/{tree}/nodes/{node_id}/dissolve")
async def dissolve_from_the_page(
    tree: str, node_id: int, request: Request, user: Admin
) -> Response:
    """Retire a topic; its contents re-enter the placement rule."""
    if not _confirmed(await _fields(request)):
        return _back(tree, node_id, error="tick the box to confirm a dissolve")
    try:
        with request.app.state.db.write() as conn:
            edits.require_node(conn, tree, node_id)
            model = str(resolve_embedding_model(conn, {})["name"])
            moved = edits.dissolve(conn, tree, node_id, model)
    except (AppError, DomainError) as exc:
        return _back(tree, node_id, error=str(exc))
    return RedirectResponse(
        f"/ui/trees/{tree}/graph?tree={tree}&done=dissolved: {moved}",
        status_code=303,
    )


@router.post("/ui/trees/{tree}/nodes/{node_id}/split")
async def split_from_the_page(
    tree: str, node_id: int, request: Request, user: Admin
) -> Response:
    """Divide a topic through the same mini-pipeline repair uses."""
    if not _confirmed(await _fields(request)):
        return _back(tree, node_id, error="tick the box to confirm a split")
    try:
        with request.app.state.db.write() as conn:
            edits.require_node(conn, tree, node_id)
            model = str(resolve_embedding_model(conn, {})["name"])
            children = edits.split(conn, tree, node_id, model)
    except (AppError, DomainError) as exc:
        return _back(tree, node_id, error=str(exc))
    # the topic they were on has retired; its children took over
    return _back(tree, children[0], done=f"split into {len(children)} topics")


@router.post("/ui/trees/{tree}/sections/{section_id}/move")
async def move_section_from_the_page(
    tree: str, section_id: int, request: Request, user: Admin
) -> Response:
    """File a chunk under the topic an operator can see it belongs to."""
    fields = await _fields(request)
    target, origin = fields.get("to_node", ""), fields.get("from_node", "")
    back = int(origin) if origin.isdigit() else 0
    if not target.isdigit():
        return _back(tree, back, error="choose a topic")
    try:
        with request.app.state.db.write() as conn:
            move = edits.move_section(conn, tree, section_id, int(target))
    except AppError as exc:
        return _back(tree, back, error=str(exc))
    emptied = " — that topic is now empty" if move.emptied else ""
    return _back(
        tree, int(target), done=f"chunk {section_id} moved here{emptied}"
    )


@router.post("/ui/trees/{tree}/nodes/{node_id}/release")
def release_from_the_page(
    tree: str, node_id: int, request: Request, user: Admin
) -> Response:
    """Hand the topic back to automation: release every pin on it."""
    with request.app.state.db.write() as conn:
        released = edits.release(conn, tree, node_id)
    return _back(tree, node_id, done=f"handed back, {released} pins released")


def _node(conn: object, tree: str, node_id: int) -> dict[str, object]:
    row = conn.execute(  # type: ignore[attr-defined]
        "SELECT level, title FROM nodes WHERE id = ?", (node_id,)
    ).fetchone()
    brief = briefs.get(conn, node_id)  # type: ignore[arg-type]
    parent = conn.execute(  # type: ignore[attr-defined]
        "SELECT parent_id FROM node_children WHERE child_id = ?", (node_id,)
    ).fetchone()
    children = [
        int(child["child_id"])
        for child in conn.execute(  # type: ignore[attr-defined]
            "SELECT child_id FROM node_children WHERE parent_id = ? "
            "ORDER BY child_id",
            (node_id,),
        ).fetchall()
    ]
    return {
        "id": node_id,
        "level": int(row["level"]),
        "title": row["title"] or _titled(brief, node_id),
        "brief": brief["text"] if brief is not None else None,
        "parent": None if parent is None else int(parent["parent_id"]),
        "children": children,
        "pins": sorted(pins.reasons(conn, node_id)),  # type: ignore[arg-type]
        "notes": notes.rendered(conn).get(node_id),  # type: ignore[arg-type]
        "members": _members(conn, node_id),
    }


def _titled(brief: object, node_id: int) -> str:
    """A topic's name: its own, else its brief's first line (0032)."""
    if brief is None:
        return f"topic {node_id}"
    first = str(brief["text"]).strip().splitlines()[0]  # type: ignore[index]
    return first[:80] or f"topic {node_id}"


def _members(conn: object, node_id: int) -> list[dict[str, object]]:
    """A topic's chunks, WORST FIT FIRST.

    `assignment_similarity` is the score a chunk was attached with, and NULL
    means a confident density-core placement (0009_nodes.sql) — so nulls sort
    LAST, not first. The operator opening a topic to see whether it is right
    wants the chunk least likely to belong at the top.
    """
    rows = conn.execute(  # type: ignore[attr-defined]
        "SELECT s.id AS id, s.path AS path, m.assignment_similarity AS score, "
        "m.forced AS forced, c.body AS body "
        "FROM node_members m JOIN sections s ON s.id = m.section_id "
        "LEFT JOIN contents c ON c.content_hash = s.content_hash "
        "WHERE m.node_id = ? "
        "ORDER BY m.assignment_similarity IS NULL, m.assignment_similarity, "
        "s.id",
        (node_id,),
    ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "path": str(row["path"]),
            "similarity": row["score"],
            "forced": bool(row["forced"]),
            "preview": _preview(row["body"]),
        }
        for row in rows
    ]


def _preview(body: object) -> str:
    if body is None:
        return "(content not stored)"
    text = bytes(body).decode("utf-8", "replace")
    return text[:PREVIEW_CHARS] + ("…" if len(text) > PREVIEW_CHARS else "")


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
