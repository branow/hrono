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

from hrono.summarize.shape import talks_back


def pending(
    conn: sqlite3.Connection, model_name: str
) -> tuple[tuple[str, bytes], ...]:
    """Return (content_hash, body) for sections not yet condensed for a model.

    Distinct section content hashes only — passage and path bodies never
    condense. A stored condensation that is the model talking back counts as
    MISSING (#221): it was cached by content hash forever, and every brief over
    that section read it as source.
    """
    rows = conn.execute(
        "SELECT DISTINCT s.content_hash AS h, c.body AS body, d.text AS text "
        "FROM sections s JOIN contents c ON c.content_hash = s.content_hash "
        "LEFT JOIN condensations d ON d.content_hash = s.content_hash "
        "AND d.model_name = ? WHERE s.source_type != 'node' "
        "ORDER BY s.content_hash",
        (model_name,),
    ).fetchall()
    return tuple(
        (row["h"], bytes(row["body"]))
        for row in rows
        if row["text"] is None or talks_back(row["text"])
    )


def unusable(
    conn: sqlite3.Connection, model_name: str
) -> tuple[tuple[str, str, str], ...]:
    """Stored condensations that fail the current gate: (hash, why, text)."""
    rows = conn.execute(
        "SELECT content_hash, text FROM condensations WHERE model_name = ? "
        "ORDER BY content_hash",
        (model_name,),
    ).fetchall()
    return tuple(
        (row["content_hash"], why, row["text"])
        for row in rows
        if (why := talks_back(row["text"]))
    )


def replace(
    conn: sqlite3.Connection,
    content_hash: str,
    model_name: str,
    text: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Store a condensation over one that was not one, staling its readers.

    A fresh key is a plain insert. A key that held a reply that talked back is
    overwritten, and every topic holding that section — and every topic above
    it, whose brief was written from those — is marked stale, so the next
    brief pass rewrites exactly the briefs that read the bad text (#221).
    """
    prior = get(conn, content_hash, model_name)
    if prior is not None and not talks_back(prior["text"]):
        return  # a good condensation is never replaced: the cache holds
    if prior is not None:
        conn.execute(
            "DELETE FROM condensations WHERE content_hash = ? "
            "AND model_name = ?",
            (content_hash, model_name),
        )
        _stale_readers(conn, content_hash)
    upsert(conn, content_hash, model_name, text, input_tokens, output_tokens)


def _stale_readers(conn: sqlite3.Connection, content_hash: str) -> None:
    conn.execute(
        "WITH RECURSIVE up(id) AS ("
        "SELECT m.node_id FROM node_members m "
        "JOIN sections s ON s.id = m.section_id WHERE s.content_hash = ? "
        "UNION SELECT c.parent_id FROM node_children c "
        "JOIN up ON c.child_id = up.id) "
        "UPDATE briefs SET stale = 1 WHERE node_id IN (SELECT id FROM up)",
        (content_hash,),
    )


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
