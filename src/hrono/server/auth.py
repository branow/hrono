"""Request-time authentication and role authorization.

The API is the only trust boundary: every protected route resolves the Bearer
token to a ``User`` and checks the user's role against the route's requirement.
A single opaque 401 covers a missing, malformed, or unknown credential so the
response never reveals which; an authenticated but under-privileged user gets a
403.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Request

from hrono.auth.users import User, authenticate
from hrono.errors import Forbidden, Unauthorized

_ROLE_RANK = {"reader": 0, "writer": 1, "admin": 2}

# The dashboard is a browser, which cannot set an Authorization header on a
# plain navigation — so it carries the SAME api token in a cookie (#180). One
# authentication path, two carriers: a second path is how "roles enforced
# server-side from day one" quietly stops being true.
#
# The cookie is set HttpOnly and SameSite=Strict at the point it is issued, so
# page scripts cannot read it and no other site can cause it to be sent. That
# last part is also what makes accepting it on the API safe: a cross-site form
# post arrives without it.
COOKIE = "hrono_token"


def _unauthenticated() -> Unauthorized:
    return Unauthorized("could not authenticate credentials")


def require_role(minimum: str) -> Callable[[Request], User]:
    """Build a dependency that authenticates then requires ``minimum`` role."""

    def dependency(request: Request) -> User:
        user = _authenticate(request)
        if _ROLE_RANK[user.role] < _ROLE_RANK[minimum]:
            raise Forbidden("insufficient role")
        return user

    return dependency


def _authenticate(request: Request) -> User:
    token = _bearer_token(
        request.headers.get("Authorization")
    ) or request.cookies.get(COOKIE)
    if not token:
        raise _unauthenticated()
    with request.app.state.db.connect() as conn:
        user = authenticate(conn, token)
    if user is None:
        raise _unauthenticated()
    return user


def _bearer_token(header: str | None) -> str | None:
    if header is None:
        return None
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()
