"""Users registry: the domain model, roles, and pure CRUD over sqlite.

Tokens are verify-only, so only a one-way hash is stored; the raw token is
returned exactly once at creation and never read back. No HTTP lives here.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from hrono.crypto.tokens import generate_token, hash_token
from hrono.db.database import tx
from hrono.errors import Conflict, Invalid, NotFound

ROLES = frozenset({"reader", "writer", "admin"})
# A name is a path segment in the panel's routes, so it has no slash, space or
# leading dot: the API and the panel refuse the same names.
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")


class InvalidRole(Invalid):
    """A role outside the allowed reader/writer/admin set (maps to 422)."""

    def __init__(self, role: str) -> None:
        super().__init__(f"invalid role: {role}")
        self.role = role


class LastAdmin(Conflict):
    """A change that would leave no admin (maps to 409)."""

    def __init__(self, name: str, what: str) -> None:
        super().__init__(
            f"{name} is the last admin: {what} would leave nobody who can "
            "manage users"
        )


@dataclass(frozen=True)
class User:
    name: str
    role: str
    created_at: str
    modified_at: str


def create_user(
    conn: sqlite3.Connection, name: str, role: str
) -> tuple[User, str]:
    """Insert a user with a fresh token; return the ``User`` and raw token once.

    The name and role are validated before any write; only the token's hash is
    persisted.
    """
    if NAME.fullmatch(name) is None:
        raise Invalid(
            "a name is letters, digits, dots, dashes and underscores, "
            "starting with a letter or digit"
        )
    if role not in ROLES:
        raise InvalidRole(role)
    token = generate_token()
    created_at = datetime.now(UTC).isoformat()
    try:
        with tx(conn):
            conn.execute(
                "INSERT INTO users (name, role, token_hash, created_at, "
                "modified_at) VALUES (?, ?, ?, ?, ?)",
                (name, role, hash_token(token), created_at, created_at),
            )
    except sqlite3.IntegrityError as exc:
        raise Conflict(f"user already exists: {name}") from exc
    return User(name, role, created_at, created_at), token


def reset_token(conn: sqlite3.Connection, name: str) -> tuple[User, str]:
    """Reissue an existing user's token; return the ``User`` and raw token once.

    Only the new token's hash is persisted (the old one stops authenticating),
    and `modified_at` moves — a rotation must leave a trace. Raises
    ``NotFound`` for an unknown user.

    The returned ``User`` carries the NEW timestamp: a caller that printed the
    one it was handed would report the moment before the rotation it just did.
    """
    user = get_user(conn, name)
    if user is None:
        raise NotFound(f"user not found: {name}")
    token = generate_token()
    modified_at = datetime.now(UTC).isoformat()
    with tx(conn):
        conn.execute(
            "UPDATE users SET token_hash = ?, modified_at = ? WHERE name = ?",
            (hash_token(token), modified_at, name),
        )
    return replace(user, modified_at=modified_at), token


def get_user(conn: sqlite3.Connection, name: str) -> User | None:
    """Return the user with ``name``, or None if there is none."""
    row = conn.execute(
        "SELECT name, role, created_at, modified_at FROM users WHERE name = ?",
        (name,),
    ).fetchone()
    return _to_user(row) if row is not None else None


def list_users(conn: sqlite3.Connection) -> tuple[User, ...]:
    """Return every user, ordered by name."""
    rows = conn.execute(
        "SELECT name, role, created_at, modified_at FROM users ORDER BY name"
    ).fetchall()
    return tuple(_to_user(row) for row in rows)


def set_role(conn: sqlite3.Connection, name: str, role: str) -> User:
    """Change ``name``'s role; the token is untouched.

    Refuses to demote the last admin: the server's one writer makes the
    check and the write a single step, so two demotions cannot each see the
    other admin still there.
    """
    if role not in ROLES:
        raise InvalidRole(role)
    with tx(conn):
        user = get_user(conn, name)
        if user is None:
            raise NotFound(f"user not found: {name}")
        if user.role == "admin" and role != "admin":
            _keep_an_admin(conn, name, "demoting them")
        modified_at = datetime.now(UTC).isoformat()
        conn.execute(
            "UPDATE users SET role = ?, modified_at = ? WHERE name = ?",
            (role, modified_at, name),
        )
    return replace(user, role=role, modified_at=modified_at)


def delete_user(conn: sqlite3.Connection, name: str) -> bool:
    """Delete the user with ``name``; return whether a row was removed.

    Refuses to delete the last admin, for the reason ``set_role`` does.
    """
    with tx(conn):
        user = get_user(conn, name)
        if user is not None and user.role == "admin":
            _keep_an_admin(conn, name, "deleting them")
        cursor = conn.execute("DELETE FROM users WHERE name = ?", (name,))
    return cursor.rowcount > 0


def authenticate(conn: sqlite3.Connection, token: str) -> User | None:
    """Return the user owning ``token``, or None for an unknown token."""
    row = conn.execute(
        "SELECT name, role, created_at, modified_at FROM users "
        "WHERE token_hash = ?",
        (hash_token(token),),
    ).fetchone()
    return _to_user(row) if row is not None else None


def _keep_an_admin(conn: sqlite3.Connection, name: str, what: str) -> None:
    others = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'admin' AND name != ?",
        (name,),
    ).fetchone()[0]
    if others == 0:
        raise LastAdmin(name, what)


def _to_user(row: sqlite3.Row) -> User:
    return User(row["name"], row["role"], row["created_at"], row["modified_at"])
