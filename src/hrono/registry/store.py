"""Generic row storage for every registry collection.

One table keyed by (collection, name); the config body is stored as JSON with
secret fields already replaced by ciphertext, and the encrypting key_id tagged
on the row.
"""

from __future__ import annotations

import sqlite3


def insert(
    conn: sqlite3.Connection,
    collection: str,
    name: str,
    config: str,
    key_id: int | None,
    now: str,
) -> None:
    """Insert a new row; raises ``sqlite3.IntegrityError`` on a duplicate."""
    with conn:
        conn.execute(
            "INSERT INTO registry "
            "(collection, name, config, key_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (collection, name, config, key_id, now, now),
        )


def replace(
    conn: sqlite3.Connection,
    collection: str,
    name: str,
    config: str,
    key_id: int | None,
    now: str,
) -> bool:
    """Replace an existing row's config; return whether a row existed."""
    with conn:
        cursor = conn.execute(
            "UPDATE registry SET config = ?, key_id = ?, updated_at = ? "
            "WHERE collection = ? AND name = ?",
            (config, key_id, now, collection, name),
        )
    return cursor.rowcount > 0


def get(
    conn: sqlite3.Connection, collection: str, name: str
) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT name, config, key_id, created_at, updated_at FROM registry "
        "WHERE collection = ? AND name = ?",
        (collection, name),
    ).fetchone()


def list_all(
    conn: sqlite3.Connection, collection: str
) -> tuple[sqlite3.Row, ...]:
    rows = conn.execute(
        "SELECT name, config, key_id, created_at, updated_at FROM registry "
        "WHERE collection = ? ORDER BY name",
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
