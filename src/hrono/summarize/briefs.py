"""Persist and read back node briefs, and gather the inputs a brief reduces.

A brief is one row per node carrying the summary text (member reference URIs
already baked in by the op), the provenance that #064 freshness and the cost API
read back (model, prompt name + template hash, token usage), and its timestamp.
``needing_brief`` drives the skip: nodes at a level with no brief yet, so a
re-run over unchanged nodes reduces nothing. The gather helpers join node
membership to the sections' condensations (the LLM input) and to the section
URIs (the mechanical references).
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime


def needing_brief(
    conn: sqlite3.Connection, tree: str, level: int
) -> tuple[int, ...]:
    """Return ids of nodes at (tree, level) that have no brief yet."""
    rows = conn.execute(
        "SELECT n.id FROM nodes n WHERE n.tree = ? AND n.level = ? "
        "AND NOT EXISTS (SELECT 1 FROM briefs b WHERE b.node_id = n.id) "
        "ORDER BY n.id",
        (tree, level),
    ).fetchall()
    return tuple(int(row["id"]) for row in rows)


def level_briefs(
    conn: sqlite3.Connection, tree: str, level: int
) -> tuple[tuple[int, str], ...]:
    """Return (node_id, brief text) for every node at (tree, level)."""
    rows = conn.execute(
        "SELECT b.node_id AS id, b.text AS text FROM briefs b "
        "JOIN nodes n ON n.id = b.node_id WHERE n.tree = ? AND n.level = ? "
        "ORDER BY b.node_id",
        (tree, level),
    ).fetchall()
    return tuple((int(row["id"]), row["text"]) for row in rows)


def member_condensations(
    conn: sqlite3.Connection, node_id: int, model_name: str
) -> tuple[str, ...]:
    """Return a node's member condensation texts (the reduce input)."""
    rows = conn.execute(
        "SELECT d.text AS text FROM node_members m "
        "JOIN sections s ON s.id = m.section_id "
        "JOIN condensations d ON d.content_hash = s.content_hash "
        "AND d.model_name = ? WHERE m.node_id = ? ORDER BY s.uri, s.id",
        (model_name, node_id),
    ).fetchall()
    return tuple(row["text"] for row in rows)


def member_uris(conn: sqlite3.Connection, node_id: int) -> tuple[str, ...]:
    """Return a node's distinct member section URIs (the mechanical refs)."""
    rows = conn.execute(
        "SELECT DISTINCT s.uri AS uri FROM node_members m "
        "JOIN sections s ON s.id = m.section_id WHERE m.node_id = ? "
        "ORDER BY s.uri",
        (node_id,),
    ).fetchall()
    return tuple(row["uri"] for row in rows)


def upsert(
    conn: sqlite3.Connection,
    node_id: int,
    text: str,
    *,
    model_name: str,
    prompt_name: str,
    prompt_hash: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Store one node's brief with its provenance."""
    conn.execute(
        "INSERT OR REPLACE INTO briefs(node_id, text, model_name, prompt_name, "
        "prompt_hash, input_tokens, output_tokens, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            node_id,
            text,
            model_name,
            prompt_name,
            prompt_hash,
            input_tokens,
            output_tokens,
            _now(),
        ),
    )


def get(conn: sqlite3.Connection, node_id: int) -> sqlite3.Row | None:
    """Return a node's brief row, or None."""
    return conn.execute(
        "SELECT node_id, text, model_name, prompt_name, prompt_hash, "
        "input_tokens, output_tokens FROM briefs WHERE node_id = ?",
        (node_id,),
    ).fetchone()


def _now() -> str:
    return datetime.now(UTC).isoformat()
