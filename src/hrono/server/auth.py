"""Request-time authentication and role authorization.

The API is the only trust boundary: every protected route resolves the Bearer
token to a ``User`` and checks the user's role against the route's requirement.
A single opaque 401 covers a missing, malformed, or unknown credential so the
response never reveals which; an authenticated but under-privileged user gets a
403.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, Request, status

from hrono.auth.users import User, authenticate

_ROLE_RANK = {"reader": 0, "writer": 1, "admin": 2}

_UNAUTHENTICATED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="could not authenticate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def require_role(minimum: str) -> Callable[[Request], User]:
    """Build a dependency that authenticates then requires ``minimum`` role."""

    def dependency(request: Request) -> User:
        user = _authenticate(request)
        if _ROLE_RANK[user.role] < _ROLE_RANK[minimum]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="insufficient role",
            )
        return user

    return dependency


def _authenticate(request: Request) -> User:
    token = _bearer_token(request.headers.get("Authorization"))
    if token is None:
        raise _UNAUTHENTICATED
    with request.app.state.db.connect() as conn:
        user = authenticate(conn, token)
    if user is None:
        raise _UNAUTHENTICATED
    return user


def _bearer_token(header: str | None) -> str | None:
    if header is None:
        return None
    scheme, _, token = header.partition(" ")
    if scheme != "Bearer" or not token.strip():
        return None
    return token.strip()
