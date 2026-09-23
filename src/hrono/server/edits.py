"""Manual-adjustment routes: the dashboard's hands (M9, T46-T48).

Admin-gated, per the spec, because every one of them overrides the pipeline's
own judgement. Each is synchronous — it touches one node and a human is
waiting — and each pins what it changed, so the next run does not undo it.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from hrono import edits
from hrono.auth.users import User
from hrono.server.auth import require_role

router = APIRouter()

Admin = Annotated[User, Depends(require_role("admin"))]


class Rename(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class BriefText(BaseModel):
    text: str = Field(min_length=1)


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
