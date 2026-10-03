"""One topic: what it says, and everything a hand can do to it.

The page (#182) and the writes (#188 edit, #189 surgery) live together because
the forms and what they post to are one subject. Every write is admin-gated,
which is the floor the API's own edit routes use — a page that took a writer
would be a second, weaker authorization for the same operation.
"""

from __future__ import annotations

import json

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, ValidationError

from hrono import edits, naming, notes, pins
from hrono.embed.model import resolve_embedding_model
from hrono.errors import AppError, DomainError, NotFound
from hrono.server import where
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


@router.get("/ui/trees/{tree}/nodes/{node_id}", response_class=HTMLResponse)
def node_page(
    tree: str,
    node_id: int,
    request: Request,
    user: Reader,
    error: str = "",
    done: str = "",
    q: str = "",
    page: int = 1,
    section: int = 0,
) -> Response:
    """One topic: what it says, where it sits, and what it is made of.

    `q` filters its sections by path and `page` pages them; `section` opens the
    page that holds one, so a link to a section survives the paging.

    `error` and `done` carry the result of a write back through the redirect,
    so the page a write lands on is a URL like any other and a refresh repeats
    nothing.
    """
    with request.app.state.db.connect() as conn:
        if not edits.node_exists(conn, tree, node_id):
            raise NotFound(f"topic not found in tree {tree}: {node_id}")
        # where every topic's sections live, read once: the page labels this
        # topic, its children AND every topic it offers to move into by it
        wheres = where.by_node(conn, tree)
        node = _node(conn, tree, node_id, wheres, q.strip(), page, section)
        candidates = _candidates(
            conn, tree, node_id, int(node["level"]), wheres
        )
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


def _candidates(
    conn: object,
    tree: str,
    node_id: int,
    level: int,
    wheres: dict[int, str],
) -> dict:
    """The topics an operator may pick, so nobody has to type an id.

    A parent sits exactly one level up and a merge partner at the same level
    (`edits.reparent`, `edits.require_one_level`). Offering anything else
    teaches the rule through a refusal, which is the worse way to learn it.

    Each one arrives the way the map names it — where its sections live, what
    it holds, what it says — because "topic 2, topic 3, topic 4" is a list of
    row ids, and nobody merges into a row id (#199).
    """

    def at(wanted: int) -> list[dict[str, object]]:
        # the NAME only, blank when a topic has none: the row prints the id
        # itself, and a fallback title of "topic 28" beside it read as
        # "topic 28 - topic 28"
        rows = conn.execute(  # type: ignore[attr-defined]
            "SELECT n.id AS id FROM nodes n WHERE n.tree = ? AND n.level = ? "
            "AND n.id != ?",
            (tree, wanted, node_id),
        ).fetchall()
        called = naming.names(conn, [int(row["id"]) for row in rows])  # type: ignore[arg-type]
        return [
            {
                "id": int(row["id"]),
                "name": called[int(row["id"])],
                "title": str(row["title"] or _first_line(row["brief"])),
                "where": wheres.get(int(row["id"]), ""),
                "holds": int(row["members"]) or int(row["kids"]),
                "holds_what": _holds_what(row["members"], row["kids"]),
            }
            for row in conn.execute(  # type: ignore[attr-defined]
                "SELECT n.id AS id, n.title AS title, b.text AS brief, "
                "(SELECT COUNT(*) FROM node_members m WHERE m.node_id = n.id)"
                " AS members, "
                "(SELECT COUNT(*) FROM node_children k "
                "WHERE k.parent_id = n.id) AS kids "
                "FROM nodes n LEFT JOIN briefs b ON b.node_id = n.id "
                "WHERE n.tree = ? AND n.level = ? AND n.id != ? ORDER BY n.id",
                (tree, wanted, node_id),
            ).fetchall()
        ]

    return {"parents": at(level + 1), "siblings": at(level)}


def _holds_what(members: object, kids: object) -> str:
    """What a topic is made of: sections at the bottom, topics above."""
    held = int(members) or int(kids)  # type: ignore[call-overload]
    noun = "section" if int(members) else "topic"  # type: ignore[call-overload]
    return noun if held == 1 else f"{noun}s"


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
    """File a section under the topic an operator can see it belongs to."""
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
        tree, int(target), done=f"section {section_id} moved here{emptied}"
    )


@router.post("/ui/trees/{tree}/nodes/{node_id}/release")
def release_from_the_page(
    tree: str, node_id: int, request: Request, user: Admin
) -> Response:
    """Hand the topic back to automation: release every pin on it."""
    with request.app.state.db.write() as conn:
        released = edits.release(conn, tree, node_id)
    return _back(tree, node_id, done=f"handed back, {released} pins released")


def _node(
    conn: object,
    tree: str,
    node_id: int,
    wheres: dict[int, str],
    q: str = "",
    page: int = 1,
    section: int = 0,
) -> dict[str, object]:
    row = conn.execute(  # type: ignore[attr-defined]
        "SELECT level, title, label, created_at FROM nodes WHERE id = ?",
        (node_id,),
    ).fetchone()
    brief = briefs.get(conn, node_id)  # type: ignore[arg-type]
    parent = conn.execute(  # type: ignore[attr-defined]
        "SELECT parent_id FROM node_children WHERE child_id = ?", (node_id,)
    ).fetchone()
    kids = naming.names(  # type: ignore[arg-type]
        conn,
        [
            int(r["child_id"])
            for r in conn.execute(  # type: ignore[attr-defined]
                "SELECT child_id FROM node_children WHERE parent_id = ?",
                (node_id,),
            ).fetchall()
        ],
    )
    children = [
        {
            "id": int(child["child_id"]),
            "name": kids[int(child["child_id"])],
            "where": wheres.get(int(child["child_id"]), ""),
            # its own name, else the first line of its brief, else its number —
            # the same ladder `_titled` walks, so the list reads like the map
            # rather than like a set of row ids
            "title": _titled_row(child, int(child["child_id"])),
            "holds": int(child["members"]) or int(child["kids"]),
            "holds_what": _holds_what(child["members"], child["kids"]),
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
    held = pins.reasons(conn, node_id)  # type: ignore[arg-type]
    return {
        "id": node_id,
        "level": int(row["level"]),
        "name": naming.name(conn, node_id),  # type: ignore[arg-type]
        "where": wheres.get(node_id, ""),
        "title": row["title"] or _titled(brief, node_id),
        "named": bool(row["title"]),
        "label": int(row["label"]),
        "born": _when(row["created_at"]),
        "brief": brief["text"] if brief is not None else None,
        # the same rule the map colours by: no brief counts as a stale one,
        # because both mean recall cannot answer from this topic
        "stale": brief is None or bool(brief["stale"]),
        "parent": _parent(conn, parent, wheres),
        "trail": _trail(conn, tree, node_id, wheres),
        "root": _is_root(conn, tree, node_id, parent),
        "children": children,
        "pin_kinds": sorted(held),
        "pins": [
            {"kind": kind, "why": held[kind] or ""} for kind in sorted(held)
        ],
        "notes": [
            {"text": text, "when": _when(when)}
            for _, text, when in notes.get(conn, notes.NODE, node_id)  # type: ignore[arg-type]
        ],
        "wrote": _provenance(conn, node_id, brief),
        "members": _members(
            conn, node_id, wheres.get(node_id, ""), brief, q, page, section
        ),
    }


def _is_root(conn: object, tree: str, node_id: int, parent: object) -> bool:
    """The tree's top: no parent, and nothing in the tree sits above it.

    A parentless topic BELOW the top is an orphan — nothing points at it — and
    keeps its warning; the root has no parent by definition.
    """
    if parent is not None:
        return False
    above = conn.execute(  # type: ignore[attr-defined]
        "SELECT 1 FROM nodes WHERE tree = ? AND level > "
        "(SELECT level FROM nodes WHERE id = ?) LIMIT 1",
        (tree, node_id),
    ).fetchone()
    return above is None


def _trail(
    conn: object, tree: str, node_id: int, wheres: dict[int, str]
) -> list[dict[str, object]]:
    """Every topic above this one, root first, named as the map names it."""
    ids: list[int] = []
    at = node_id
    while True:
        up = conn.execute(  # type: ignore[attr-defined]
            "SELECT parent_id FROM node_children WHERE child_id = ?", (at,)
        ).fetchone()
        if up is None or int(up["parent_id"]) in ids:
            break
        at = int(up["parent_id"])
        ids.append(at)
    return [
        {
            "id": above,
            "name": naming.name(conn, above),  # type: ignore[arg-type]
            "where": wheres.get(above, ""),
        }
        for above in reversed(ids)
    ]


def _parent(
    conn: object, row: object, wheres: dict[int, str]
) -> dict[str, object] | None:
    """The topic above, named the way the map names it rather than by id."""
    if row is None:
        return None
    parent_id = int(row["parent_id"])  # type: ignore[index]
    named = conn.execute(  # type: ignore[attr-defined]
        "SELECT n.id AS id, n.title AS title, b.text AS brief FROM nodes n "
        "LEFT JOIN briefs b ON b.node_id = n.id WHERE n.id = ?",
        (parent_id,),
    ).fetchone()
    return {
        "id": parent_id,
        "name": naming.name(conn, parent_id),  # type: ignore[arg-type]
        "where": wheres.get(parent_id, ""),
        "title": _titled_row(named, parent_id),
    }


def _provenance(
    conn: object, node_id: int, brief: object
) -> dict[str, object] | None:
    """Who wrote this brief, from what, at what cost, and whether it holds.

    The freshness columns are the whole incremental mechanism (#064, #191), and
    an operator looking at a brief they distrust wants exactly them: the model
    and the prompt that wrote it, and whether the members it was written over
    are still the members it has.
    """
    if brief is None:
        return None
    row = conn.execute(  # type: ignore[attr-defined]
        "SELECT created_at FROM briefs WHERE node_id = ?", (node_id,)
    ).fetchone()
    signed = str(brief["member_signature"] or "")  # type: ignore[index]
    now = briefs.member_signature(conn, node_id)  # type: ignore[arg-type]
    return {
        "model": str(brief["model_name"]),  # type: ignore[index]
        "fingerprint": _short(brief["model_fingerprint"]),  # type: ignore[index]
        "prompt": str(brief["prompt_name"]),  # type: ignore[index]
        "prompt_hash": _short(brief["prompt_hash"]),  # type: ignore[index]
        "tokens_in": int(brief["input_tokens"]),  # type: ignore[index]
        "tokens_out": int(brief["output_tokens"]),  # type: ignore[index]
        "written": _when(row["created_at"]) if row is not None else "",
        "signature": _short(signed),
        "moved": bool(signed) and signed != now,
        "marked": bool(brief["stale"]),  # type: ignore[index]
        "flagged": briefs.unusable(conn, brief),  # type: ignore[arg-type]
        "unsupported": _listed(brief["unfaithful"]),  # type: ignore[index]
        "cites": len(_listed(brief["members"])),  # type: ignore[index]
    }


def _listed(column: object) -> list[str]:
    """A JSON-array column, as a list — an empty one when it is not readable."""
    try:
        loaded = json.loads(str(column or "[]"))
    except ValueError:
        return []
    return [str(item) for item in loaded] if isinstance(loaded, list) else []


def _short(digest: object) -> str:
    """A hash an operator can compare by eye, not one that fills a column."""
    return str(digest)[:12] if digest else ""


def _when(stamp: object) -> str:
    """An ISO timestamp as a minute, which is the resolution anyone reads."""
    text = str(stamp or "")
    if "T" not in text:
        return text
    day, clock = text.split("T", 1)
    return f"{day} {clock[:5]}"


TITLE_CHARS = 80


def _titled(brief: object, node_id: int) -> str:
    """A topic's name: its own, else its brief's first line (0032)."""
    if brief is None:
        return f"topic {node_id}"
    first = str(brief["text"]).strip().splitlines()[0]  # type: ignore[index]
    return _clipped(first) or f"topic {node_id}"


def _titled_row(row: object, node_id: int) -> str:
    """The same ladder, for a row that already carries its title and brief."""
    own = row["title"]  # type: ignore[index]
    if own:
        return str(own)
    return _first_line(row["brief"]) or f"topic {node_id}"  # type: ignore[index]


def _first_line(brief: object) -> str:
    """A brief's opening line, clipped: the name a topic with none gets."""
    if not brief:
        return ""
    return _clipped(str(brief).strip().splitlines()[0])


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


SECTION_PAGE = 25
HEADING_CHARS = 60


def _members(
    conn: object,
    node_id: int,
    stem: str,
    brief: object,
    q: str,
    page: int,
    focus: int,
) -> dict[str, object]:
    """A topic's sections, WORST FIT FIRST, one page of them.

    `assignment_similarity` is the score a section was attached with, and NULL
    means a confident density-core placement (0009_nodes.sql) — so nulls sort
    LAST, not first. The operator opening a topic to see whether it is right
    wants the section least likely to belong at the top.

    `q` keeps the sections whose path contains it. `focus` is a section a link
    points at: the page that holds it is the one shown.
    """
    held = conn.execute(  # type: ignore[attr-defined]
        "SELECT COUNT(*) FROM node_members WHERE node_id = ?", (node_id,)
    ).fetchone()[0]
    ordered = [
        int(row["id"])
        for row in conn.execute(  # type: ignore[attr-defined]
            "SELECT s.id AS id FROM node_members m "
            "JOIN sections s ON s.id = m.section_id "
            "WHERE m.node_id = ? AND instr(lower(s.path), ?) > 0 "
            "ORDER BY m.assignment_similarity IS NULL, "
            "m.assignment_similarity, s.id",
            (node_id, q.lower()),
        ).fetchall()
    ]
    pages = max(1, -(-len(ordered) // SECTION_PAGE))
    if focus in ordered:
        page = ordered.index(focus) // SECTION_PAGE + 1
    page = min(max(page, 1), pages)
    wanted = ordered[(page - 1) * SECTION_PAGE : page * SECTION_PAGE]
    model = briefs.condense_model(conn, node_id)  # type: ignore[arg-type]
    rows = {
        int(row["id"]): row
        for row in conn.execute(  # type: ignore[attr-defined]
            "SELECT s.id AS id, s.source AS source, s.path AS path, "
            "s.version AS version, s.uri AS uri, "
            "s.byte_start AS start, s.byte_end AS stop, "
            "m.assignment_similarity AS score, "
            "m.forced AS forced, c.body AS body, "
            # the MIDDLE of the pipeline: what the topic's brief was actually
            # reduced from — the condensation by the model the brief RECORDED,
            # so a section condensed by two models is still one row (#197)
            "d.text AS condensed, d.model_name AS condensed_by "
            "FROM node_members m JOIN sections s ON s.id = m.section_id "
            "LEFT JOIN contents c ON c.content_hash = s.content_hash "
            "LEFT JOIN condensations d ON d.content_hash = s.content_hash "
            "AND d.model_name = (SELECT x.model_name FROM condensations x "
            "WHERE x.content_hash = s.content_hash "
            "ORDER BY x.model_name = ? DESC, x.model_name LIMIT 1) "
            f"WHERE m.node_id = ? AND s.id IN ({','.join('?' * len(wanted))})",  # noqa: S608
            (model, node_id, *wanted),
        ).fetchall()
    }
    starts = _line_starts(conn, [rows[i] for i in wanted])
    return {
        "rows": [_member(rows[i], stem, starts[i]) for i in wanted],
        "total": int(held),
        "matched": len(ordered),
        "page": page,
        "pages": pages,
        "q": q,
    }


def _line_starts(conn: object, rows: list[object]) -> dict[int, int]:
    """The line each section begins on, counted from the file's own start.

    A file is the sections laid end to end, so the lines before one are the
    newlines in the sections before it.
    """
    files = {
        (str(r["source"]), str(r["path"]), str(r["version"]))  # type: ignore[index]
        for r in rows
    }
    before: dict[tuple[str, str, str], list[tuple[int, int]]] = {}
    for source, path, version in files:
        before[(source, path, version)] = [
            (int(r["start"]), bytes(r["body"] or b"").count(b"\n"))
            for r in conn.execute(  # type: ignore[attr-defined]
                "SELECT s.byte_start AS start, c.body AS body "
                "FROM sections s LEFT JOIN contents c "
                "ON c.content_hash = s.content_hash "
                "WHERE s.source = ? AND s.path = ? AND s.version = ?",
                (source, path, version),
            ).fetchall()
        ]
    return {
        int(r["id"]): 1  # type: ignore[index]
        + sum(
            lines
            for start, lines in before[
                (str(r["source"]), str(r["path"]), str(r["version"]))  # type: ignore[index]
            ]
            if start < int(r["start"])  # type: ignore[index]
        )
        for r in rows
    }


def _heading(body: object) -> str:
    """Where a section starts, in the file's own words: its first real line."""
    if body is None:
        return ""
    for line in bytes(body).decode("utf-8", "replace").splitlines():
        words = line.strip().lstrip("#").strip()
        if words:
            return (
                words
                if len(words) <= HEADING_CHARS
                else (words[: HEADING_CHARS - 1].rstrip() + "\u2026")
            )
    return ""


def _member(row: object, where: str, first: int) -> dict[str, object]:
    """One section, its path split where it stops saying what its topic said.

    Thirty-five rows opening with the same twenty characters are thirty-five
    rows nobody scans, so the shared directory is set apart from the part that
    tells them apart (#198), and what tells two sections of one file apart —
    where each starts and how far it runs — is beside it (#214).
    """
    path = str(row["path"])  # type: ignore[index]
    shared = f"{where}/" if where and path.startswith(f"{where}/") else ""
    body = row["body"]  # type: ignore[index]
    raw = bytes(body or b"")
    last = first + max(raw.count(b"\n") + (not raw.endswith(b"\n")) - 1, 0)
    return {
        "id": int(row["id"]),  # type: ignore[index]
        "path": path,
        "uri": str(row["uri"]),  # type: ignore[index]
        "stem": shared,
        "tail": path.removeprefix(shared),
        "heading": _heading(body),
        "lines": f"{first}-{last}" if last > first else str(first),
        "bytes": int(row["stop"]) - int(row["start"]),  # type: ignore[index]
        "similarity": row["score"],  # type: ignore[index]
        "forced": bool(row["forced"]),  # type: ignore[index]
        "content": _content(body),
        "condensed": _condensation(row),
    }


def _condensation(row: object) -> dict[str, object] | None:
    """What a model wrote about this section, and which model wrote it.

    None when the condense stage has not reached it — the common case on a
    part-built tree, and a case the page must say out loud rather than render
    as an empty panel.
    """
    text = row["condensed"]  # type: ignore[index]
    if not text:
        return None
    return {
        "text": str(text),
        "by": str(row["condensed_by"]),  # type: ignore[index]
    }
    # The GOTCHA lines used to be lifted out and printed above the text as
    # warning callouts. The text that follows is three paragraphs long and
    # OPENS with the same lines, so the page said each hazard twice and put
    # the duplicate first — the reader met the ending before the beginning
    # (#200). A hazard that is already the first thing in the condensation
    # does not need lifting out of it.


def _content(body: object) -> dict[str, object]:
    """What a section actually says — the WHOLE of it.

    It used to stop at 4,000 characters and say how many it was holding back.
    But a section is already the unit the splitter chose precisely because it
    is a readable amount of one file, the pane it lands in is a scrolling box
    inside a `<details>` nobody opens by accident, and the one thing a reader
    opens a section FOR is the part the cut removed (#200).
    """
    if body is None:
        return {"text": "", "total": 0, "missing": True}
    text = bytes(body).decode("utf-8", "replace")
    return {"text": text, "total": len(text), "missing": False}
