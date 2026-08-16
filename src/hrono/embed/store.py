"""Persist and read back content vectors, keyed by (hash, model_name).

A vector is stored once per model as a float32 blob; re-storing the same key is
a no-op, so embedding is idempotent. ``missing`` drives the incremental skip: it
returns the content hashes that have no vector for the target model yet, so a
re-run embeds nothing and a model swap embeds everything under the new key.
"""

from __future__ import annotations

import sqlite3
from array import array
from collections.abc import Sequence
from datetime import UTC, datetime


def missing(conn: sqlite3.Connection, model_name: str) -> tuple[str, ...]:
    """Return content hashes with no vector for ``model_name`` yet."""
    rows = conn.execute(
        "SELECT c.content_hash FROM contents c WHERE NOT EXISTS ("
        "SELECT 1 FROM embeddings e WHERE e.content_hash = c.content_hash "
        "AND e.model_name = ?) ORDER BY c.content_hash",
        (model_name,),
    ).fetchall()
    return tuple(row["content_hash"] for row in rows)


def upsert_vector(
    conn: sqlite3.Connection,
    content_hash: str,
    model_name: str,
    vector: Sequence[float],
) -> None:
    """Store one vector once; a repeat (hash, model) key is a no-op."""
    blob = array("f", vector).tobytes()
    conn.execute(
        "INSERT OR IGNORE INTO embeddings(content_hash, model_name, dims, "
        "vector, created_at) VALUES (?, ?, ?, ?, ?)",
        (content_hash, model_name, len(vector), blob, _now()),
    )


def get_vector(
    conn: sqlite3.Connection, content_hash: str, model_name: str
) -> tuple[float, ...] | None:
    """Return a stored vector as floats, or None."""
    row = conn.execute(
        "SELECT vector FROM embeddings WHERE content_hash = ? "
        "AND model_name = ?",
        (content_hash, model_name),
    ).fetchone()
    if row is None:
        return None
    values = array("f")
    values.frombytes(row["vector"])
    return tuple(values)


def vector_count(conn: sqlite3.Connection, model_name: str) -> int:
    """Return how many vectors are stored for a model."""
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM embeddings WHERE model_name = ?",
            (model_name,),
        ).fetchone()[0]
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
