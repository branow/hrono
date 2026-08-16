"""Users registry: the domain model, roles, and pure CRUD over sqlite.

Tokens are verify-only, so only a one-way hash is stored; the raw token is
returned exactly once at creation and never read back. No HTTP lives here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from hrono.crypto.tokens import generate_token, hash_token
from hrono.errors import Conflict, Invalid, NotFound

ROLES = frozenset({"reader", "writer", "admin"})


class InvalidRole(Invalid):
    """A role outside the allowed reader/writer/admin set (maps to 422)."""

    def __init__(self, role: str) -> None:
        super().__init__(f"invalid role: {role}")
        self.role = role


@dataclass(frozen=True)
class User:
    name: str
    role: str
    created_at: str


def create_user(
    conn: sqlite3.Connection, name: str, role: str
) -> tuple[User, str]:
    """Insert a user with a fresh token; return the ``User`` and raw token once.

    The role is validated before any write; only the token's hash is persisted.
    """
    if role not in ROLES:
        raise InvalidRole(role)
    token = generate_token()
    created_at = datetime.now(UTC).isoformat()
    try:
        with conn:
            conn.execute(
                "INSERT INTO users (name, role, token_hash, created_at) "
                "VALUES (?, ?, ?, ?)",
                (name, role, hash_token(token), created_at),
            )
    except sqlite3.IntegrityError as exc:
        raise Conflict(f"user already exists: {name}") from exc
    return User(name, role, created_at), token


def reset_token(conn: sqlite3.Connection, name: str) -> tuple[User, str]:
    """Reissue an existing user's token; return the ``User`` and raw token once.

    Only the new token's hash is persisted (the old one stops authenticating);
    no other column or row changes. Raises ``NotFound`` for an unknown user.
    """
    user = get_user(conn, name)
    if user is None:
        raise NotFound(f"user not found: {name}")
    token = generate_token()
    with conn:
        conn.execute(
            "UPDATE users SET token_hash = ? WHERE name = ?",
            (hash_token(token), name),
        )
    return user, token


def get_user(conn: sqlite3.Connection, name: str) -> User | None:
    """Return the user with ``name``, or None if there is none."""
    row = conn.execute(
        "SELECT name, role, created_at FROM users WHERE name = ?", (name,)
    ).fetchone()
    return _to_user(row) if row is not None else None


def list_users(conn: sqlite3.Connection) -> tuple[User, ...]:
    """Return every user, ordered by name."""
    rows = conn.execute(
        "SELECT name, role, created_at FROM users ORDER BY name"
    ).fetchall()
    return tuple(_to_user(row) for row in rows)


def delete_user(conn: sqlite3.Connection, name: str) -> bool:
    """Delete the user with ``name``; return whether a row was removed."""
    with conn:
        cursor = conn.execute("DELETE FROM users WHERE name = ?", (name,))
    return cursor.rowcount > 0


def authenticate(conn: sqlite3.Connection, token: str) -> User | None:
    """Return the user owning ``token``, or None for an unknown token."""
    row = conn.execute(
        "SELECT name, role, created_at FROM users WHERE token_hash = ?",
        (hash_token(token),),
    ).fetchone()
    return _to_user(row) if row is not None else None


def _to_user(row: sqlite3.Row) -> User:
    return User(row["name"], row["role"], row["created_at"])
