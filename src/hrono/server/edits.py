"""Manual-adjustment routes: the dashboard's hands (M9, T46-T48).

Admin-gated, per the spec, because every one of them overrides the pipeline's
own judgement. Each is synchronous — it touches one node and a human is
waiting — and each pins what it changed, so the next run does not undo it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from hrono import edits, notes
from hrono.auth.users import User
from hrono.embed.model import resolve_embedding_model
from hrono.server.auth import require_role

router = APIRouter()

Admin = Annotated[User, Depends(require_role("admin"))]
Reader = Annotated[User, Depends(require_role("reader"))]


class Rename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class BriefText(BaseModel):
    text: str = Field(min_length=1)


class NoteText(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class Reparent(BaseModel):
    to: int


class Merge(BaseModel):
    ids: list[int] = Field(min_length=2)


@router.patch("/trees/{name}/nodes/{node_id}")
def rename_node(
    name: str, node_id: int, body: Rename, request: Request, _: Admin
) -> dict[str, object]:
    """Name a topic; the export shows this instead of the derived title."""
    with request.app.state.db.write() as conn:
        edits.rename(conn, name, node_id, body.title)
    return {"node_id": node_id, "title": body.title, "pinned": True}


@router.put("/trees/{name}/nodes/{node_id}/brief")
def override_brief(
    name: str, node_id: int, body: BriefText, request: Request, _: Admin
) -> dict[str, object]:
    """Replace a node's brief with the operator's own words (pins)."""
    with request.app.state.db.write() as conn:
        edits.override_brief(conn, name, node_id, body.text)
    return {"node_id": node_id, "pinned": True}


@router.post("/trees/{name}/nodes/{node_id}/unpin")
def unpin_node(
    name: str, node_id: int, request: Request, _: Admin
) -> dict[str, object]:
    """Hand the node back to automation."""
    with request.app.state.db.write() as conn:
        released = edits.release(conn, name, node_id)
    return {"node_id": node_id, "released": released}


@router.post("/trees/{name}/nodes/{node_id}/notes")
def note_node(
    name: str, node_id: int, body: NoteText, request: Request, _: Admin
) -> dict[str, object]:
    """Annotate a topic; the export shows it to the traversing agent."""
    with request.app.state.db.write() as conn:
        edits.require_node(conn, name, node_id)
        note_id = notes.add(conn, notes.NODE, node_id, body.text)
    return {"note_id": note_id, "node_id": node_id}


@router.post("/trees/{name}/sections/{section_id}/notes")
def note_section(
    name: str, section_id: int, body: NoteText, request: Request, _: Admin
) -> dict[str, object]:
    """Annotate one chunk of a source."""
    with request.app.state.db.write() as conn:
        edits.require_section(conn, section_id)
        note_id = notes.add(conn, notes.SECTION, section_id, body.text)
    return {"note_id": note_id, "section_id": section_id}


@router.get("/trees/{name}/nodes/{node_id}/notes")
def read_node_notes(
    name: str, node_id: int, request: Request, _: Reader
) -> dict[str, object]:
    """A topic's notes, newest first."""
    with request.app.state.db.connect() as conn:
        edits.require_node(conn, name, node_id)
        found = notes.get(conn, notes.NODE, node_id)
    return {"notes": [_note(row) for row in found]}


@router.get("/trees/{name}/sections/{section_id}/notes")
def read_section_notes(
    name: str, section_id: int, request: Request, _: Reader
) -> dict[str, object]:
    """A section's notes, newest first."""
    with request.app.state.db.connect() as conn:
        edits.require_section(conn, section_id)
        found = notes.get(conn, notes.SECTION, section_id)
    return {"notes": [_note(row) for row in found]}


def _note(row: tuple[int, str, str]) -> dict[str, object]:
    note_id, text, created_at = row
    return {"id": note_id, "text": text, "created_at": created_at}


@router.post("/trees/{name}/nodes/{node_id}/reparent")
def reparent_node(
    name: str, node_id: int, body: Reparent, request: Request, _: Admin
) -> dict[str, object]:
    """Hang a topic under a chosen parent (pins)."""
    with request.app.state.db.write() as conn:
        edits.reparent(conn, name, node_id, body.to)
    return {"node_id": node_id, "parent_id": body.to, "pinned": True}


@router.post("/trees/{name}/nodes/merge")
def merge_nodes(
    name: str, body: Merge, request: Request, _: Admin
) -> dict[str, object]:
    """Fold topics into one; the lowest id survives."""
    with request.app.state.db.write() as conn:
        survivor = edits.merge(conn, name, body.ids)
    return {"node_id": survivor, "merged": sorted(set(body.ids))}


@router.post("/trees/{name}/nodes/{node_id}/dissolve")
def dissolve_node(
    name: str, node_id: int, request: Request, _: Admin
) -> dict[str, object]:
    """Retire a topic; its members re-enter the placement rule.

    The node is confirmed before the embedding model is resolved, so an
    unknown id is a 404 rather than the 500 a server with no model gave.
    """
    with request.app.state.db.write() as conn:
        edits.require_node(conn, name, node_id)
        model = str(resolve_embedding_model(conn, {})["name"])
        members = edits.dissolve(conn, name, node_id, model)
    return {"node_id": node_id, "members": members}


@router.post("/trees/{name}/nodes/{node_id}/split")
def split_node(
    name: str, node_id: int, request: Request, _: Admin
) -> dict[str, object]:
    """Divide a topic; the old node retires, its children take over.

    The node is confirmed BEFORE the embedding model is resolved: a server
    with no embedding model answered an unknown node with a 500, because the
    model it did not need yet was the first thing it went looking for.
    """
    with request.app.state.db.write() as conn:
        edits.require_node(conn, name, node_id)
        model = str(resolve_embedding_model(conn, {})["name"])
        children = edits.split(conn, name, node_id, model)
    return {"node_id": node_id, "children": list(children)}
