"""First-run bootstrap: mint an admin token when the users table is empty.

This resolves the chicken-and-egg lock on a fresh install (no user can
authenticate to create the first user). It fires exactly once over a database's
lifetime: empty table -> mint one admin; never again while any user exists.
"""

from __future__ import annotations

import sqlite3

from hrono.auth.users import create_user

BOOTSTRAP_ADMIN = "admin"


def bootstrap_admin(conn: sqlite3.Connection) -> str | None:
    """Mint the bootstrap admin if no users exist; return its raw token once.

    Returns the raw token when a fresh ``admin`` is created, or None when the
    users table already holds any user (idempotent across restarts). The raw
    token is returned to the caller only; only its hash is ever persisted.
    """
    if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone() is not None:
        return None
    _, token = create_user(conn, BOOTSTRAP_ADMIN, "admin")
    return token
