"""Generic row storage for every registry collection.

One table keyed by (collection, name); the config body is stored as JSON with
secret fields already replaced by ciphertext, the encrypting key_id tagged, a
``content_hash`` for later invalidation, and an ``is_default`` flag marking a
seeded default (which DELETE resets rather than removes).
"""

from __future__ import annotations

import sqlite3

_COLUMNS = (
    "name, config, key_id, created_at, updated_at, is_default, content_hash"
)


def insert(
    conn: sqlite3.Connection,
    collection: str,
    name: str,
    config: str,
    key_id: int | None,
    now: str,
    is_default: int = 0,
    content_hash: str | None = None,
) -> None:
    """Insert a new row; raises ``sqlite3.IntegrityError`` on a duplicate."""
    with conn:
        conn.execute(
            "INSERT INTO registry (collection, name, config, key_id, "
            "created_at, updated_at, is_default, content_hash) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                collection,
                name,
                config,
                key_id,
                now,
                now,
                is_default,
                content_hash,
            ),
        )


def replace(
    conn: sqlite3.Connection,
    collection: str,
    name: str,
    config: str,
    key_id: int | None,
    now: str,
    content_hash: str | None = None,
) -> bool:
    """Replace a row's config (is_default kept); return whether it existed."""
    with conn:
        cursor = conn.execute(
            "UPDATE registry SET config = ?, key_id = ?, updated_at = ?, "
            "content_hash = ? WHERE collection = ? AND name = ?",
            (config, key_id, now, content_hash, collection, name),
        )
    return cursor.rowcount > 0


def get(
    conn: sqlite3.Connection, collection: str, name: str
) -> sqlite3.Row | None:
    return conn.execute(
        f"SELECT {_COLUMNS} FROM registry WHERE collection = ? AND name = ?",
        (collection, name),
    ).fetchone()


def list_all(
    conn: sqlite3.Connection, collection: str
) -> tuple[sqlite3.Row, ...]:
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM registry WHERE collection = ? ORDER BY name",
        (collection,),
    ).fetchall()
    return tuple(rows)


def delete(conn: sqlite3.Connection, collection: str, name: str) -> bool:
    with conn:
        cursor = conn.execute(
            "DELETE FROM registry WHERE collection = ? AND name = ?",
            (collection, name),
        )
    return cursor.rowcount > 0
