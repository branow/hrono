"""Persist and read back per-section condensations, keyed (content_hash, model).

``pending`` drives the incremental skip exactly like the embeddings store: it
returns the distinct SECTION content hashes (bodies, not passages or paths) that
have no condensation for the target model yet, so a re-run condenses nothing and
a model swap re-condenses under the new key. ``upsert`` stores one condensation
once; a repeat key is a no-op.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


def pending(
    conn: sqlite3.Connection, model_name: str
) -> tuple[tuple[str, bytes], ...]:
    """Return (content_hash, body) for sections not yet condensed for a model.

    Distinct section content hashes only — passage and path bodies never
    condense.
    """
    rows = conn.execute(
        "SELECT DISTINCT s.content_hash AS h, c.body AS body "
        "FROM sections s JOIN contents c ON c.content_hash = s.content_hash "
        "WHERE NOT EXISTS (SELECT 1 FROM condensations d "
        "WHERE d.content_hash = s.content_hash AND d.model_name = ?) "
        "ORDER BY s.content_hash",
        (model_name,),
    ).fetchall()
    return tuple((row["h"], bytes(row["body"])) for row in rows)


def upsert(
    conn: sqlite3.Connection,
    content_hash: str,
    model_name: str,
    text: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Store one condensation; a repeat (hash, model) key is a no-op."""
    conn.execute(
        "INSERT OR IGNORE INTO condensations(content_hash, model_name, text, "
        "input_tokens, output_tokens, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (content_hash, model_name, text, input_tokens, output_tokens, _now()),
    )


def get(
    conn: sqlite3.Connection, content_hash: str, model_name: str
) -> sqlite3.Row | None:
    """Return a stored condensation row, or None."""
    return conn.execute(
        "SELECT text, input_tokens, output_tokens FROM condensations "
        "WHERE content_hash = ? AND model_name = ?",
        (content_hash, model_name),
    ).fetchone()


def count(conn: sqlite3.Connection, model_name: str) -> int:
    """Return how many condensations are stored for a model."""
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM condensations WHERE model_name = ?",
            (model_name,),
        ).fetchone()[0]
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
