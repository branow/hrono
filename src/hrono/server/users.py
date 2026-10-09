"""Users routes: list (reader+), create (admin), delete (admin).

Reads never expose a token or its hash; create returns the freshly minted raw
token exactly once. Domain errors map to actionable status codes, never a 500.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel

from hrono.auth.users import User, create_user, delete_user, list_users
from hrono.errors import NotFound
from hrono.server.auth import require_role
from hrono.server.rotation import rotate_running

router = APIRouter()

Reader = Annotated[User, Depends(require_role("reader"))]
Admin = Annotated[User, Depends(require_role("admin"))]


class UserCreate(BaseModel):
    name: str
    role: str


def _public(user: User) -> dict[str, str]:
    return {
        "name": user.name,
        "role": user.role,
        "created_at": user.created_at,
        "modified_at": user.modified_at,
    }


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
    with request.app.state.db.write() as conn:
        user, token = create_user(conn, body.name, body.role)
    return {**_public(user), "token": token}


@router.delete("/users/{name}")
def delete_named_user(
    name: str,
    request: Request,
    _: Admin,
) -> dict[str, str]:
    with request.app.state.db.write() as conn:
        removed = delete_user(conn, name)
    if not removed:
        raise NotFound(f"user not found: {name}")
    return {"deleted": name}


class RotateKey(BaseModel):
    old_key: str
    new_key: str


@router.post("/admin/rotate-key")
def rotate_master_key(
    body: RotateKey, request: Request, _: Admin
) -> dict[str, object]:
    """Re-encrypt every secret under a new master key.

    Synchronous rather than a queued job, deliberately: a
    job's ``scope`` is persisted, and the inputs here are two master keys. The
    secret-bearing rows are registry config — tens of them, not millions.

    The running server switches to the new key as part of the same call
    (`rotate_running`), so a secret saved before the restart is tagged with the
    new key_id and survives it. The key FILE is the operator's: the next start
    reconciles against the new fingerprint and refuses the old key, which is
    the protection working rather than a surprise.
    """
    result = rotate_running(
        request.app, body.old_key.encode(), body.new_key.encode()
    )
    return {
        "key_id": result.key_id,
        "rotated": result.rows,
        "next": (
            "this server already runs on the new key, so a credential saved "
            "now is on it; update the key file and RESTART on it, because "
            "the next start refuses the old key"
        ),
    }
