"""Users routes: list (reader+), create (admin), delete (admin).

Reads never expose a token or its hash; create returns the freshly minted raw
token exactly once. Domain errors map to actionable status codes, never a 500.
"""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from hrono.auth.users import (
    InvalidRole,
    User,
    create_user,
    delete_user,
    list_users,
)
from hrono.server.auth import require_role

router = APIRouter()

Reader = Annotated[User, Depends(require_role("reader"))]
Admin = Annotated[User, Depends(require_role("admin"))]


class UserCreate(BaseModel):
    name: str
    role: str


def _public(user: User) -> dict[str, str]:
    return {"name": user.name, "role": user.role, "created_at": user.created_at}


@router.get("/users")
def get_users(request: Request, _: Reader) -> list[dict[str, str]]:
    with request.app.state.db.connect() as conn:
        return [_public(user) for user in list_users(conn)]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def post_user(
    body: UserCreate,
    request: Request,
    _: Admin,
) -> dict[str, str]:
    try:
        with request.app.state.db.connect() as conn:
            user, token = create_user(conn, body.name, body.role)
    except InvalidRole as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"invalid role: {exc.role}",
        ) from exc
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"user already exists: {body.name}",
        ) from exc
    return {**_public(user), "token": token}


@router.delete("/users/{name}")
def delete_named_user(
    name: str,
    request: Request,
    _: Admin,
) -> dict[str, str]:
    with request.app.state.db.connect() as conn:
        removed = delete_user(conn, name)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"user not found: {name}",
        )
    return {"deleted": name}
