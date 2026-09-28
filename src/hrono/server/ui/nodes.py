"""One topic: what it says, and everything a hand can do to it.

The page (#182) and the writes (#188 edit, #189 surgery) live together because
the forms and what they post to are one subject. Every write is admin-gated,
which is the floor the API's own edit routes use — a page that took a writer
would be a second, weaker authorization for the same operation.
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, ValidationError

from hrono import edits, notes, pins
from hrono.embed.model import resolve_embedding_model
from hrono.errors import AppError, DomainError, NotFound
from hrono.server.edits import BriefText, NoteText, Rename
from hrono.server.ui import (
    Admin,
    Reader,
    _back,
    _fields,
    _trees,
    router,
    templates,
)
from hrono.summarize import briefs

# Enough to recognise a chunk, not enough to lose the topic off the screen. A
# section is ~10 KB and a topic can hold thirty of them (#182).
PREVIEW_CHARS = 600


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
        # the NAME only, blank when a topic has none: the page prints the id
        # itself, and a fallback title of "topic 28" beside it read as
        # "topic 28 - topic 28"
        return [
            {
                "id": int(row["id"]),
                "title": str(row["title"] or ""),
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
        {
            "id": int(child["child_id"]),
            # its own name, else the first line of its brief, else its number —
            # the same ladder `_titled` walks, so the list reads like the map
            # rather than like a set of row ids
            "title": _titled_row(child),
            "holds": int(child["members"]) or int(child["kids"]),
            "holds_what": "chunks" if int(child["members"]) else "topics",
        }
        for child in conn.execute(  # type: ignore[attr-defined]
            "SELECT c.child_id AS child_id, n.title AS title, b.text AS brief, "
            "(SELECT COUNT(*) FROM node_members m WHERE m.node_id = c.child_id)"
            " AS members, "
            "(SELECT COUNT(*) FROM node_children k "
            "WHERE k.parent_id = c.child_id) AS kids "
            "FROM node_children c JOIN nodes n ON n.id = c.child_id "
            "LEFT JOIN briefs b ON b.node_id = c.child_id "
            "WHERE c.parent_id = ? ORDER BY c.child_id",
            (node_id,),
        ).fetchall()
    ]
    return {
        "id": node_id,
        "level": int(row["level"]),
        "title": row["title"] or _titled(brief, node_id),
        "brief": brief["text"] if brief is not None else None,
        # the same rule the map colours by: no brief counts as a stale one,
        # because both mean recall cannot answer from this topic
        "stale": brief is None or bool(brief["stale"]),
        "parent": None if parent is None else int(parent["parent_id"]),
        "children": children,
        "pins": sorted(pins.reasons(conn, node_id)),  # type: ignore[arg-type]
        "notes": notes.rendered(conn).get(node_id),  # type: ignore[arg-type]
        "members": _members(conn, node_id),
    }


TITLE_CHARS = 80


def _titled(brief: object, node_id: int) -> str:
    """A topic's name: its own, else its brief's first line (0032)."""
    if brief is None:
        return f"topic {node_id}"
    first = str(brief["text"]).strip().splitlines()[0]  # type: ignore[index]
    return _clipped(first) or f"topic {node_id}"


def _titled_row(row: object) -> str:
    """The same ladder, for a row that already carries its title and brief."""
    own = row["title"]  # type: ignore[index]
    if own:
        return str(own)
    brief = row["brief"]  # type: ignore[index]
    if brief:
        return _clipped(str(brief).strip().splitlines()[0])
    return f"topic {int(row['child_id'])}"  # type: ignore[index]


def _clipped(text: str) -> str:
    """Cut a long title at a word, and SAY it was cut.

    A heading that stops mid-clause reads as a rendering fault rather than as
    a summary someone abbreviated.
    """
    if len(text) <= TITLE_CHARS:
        return text
    cut = text[: TITLE_CHARS - 1]
    spaced = cut.rsplit(" ", 1)[0] if " " in cut[-20:] else cut
    return spaced.rstrip(" ,;:.") + "\u2026"


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
