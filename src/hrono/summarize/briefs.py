"""Persist and read back node briefs, and gather the inputs a brief reduces.

A brief is one row per node carrying the summary text (member reference URIs
already baked in by the op), the provenance the cost API reads back (model,
prompt name + template hash, token usage), the member-set signature it was
written against, and its timestamp. ``stale_or_missing`` drives incremental
regeneration: a node needs a brief when it has none, or when its members or its
prompt/model have changed since the brief was written (T23.2). The gather
helpers join node membership to the sections' condensations (the LLM input) and
to the section URIs (the mechanical references).
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime


def member_signature(conn: sqlite3.Connection, node_id: int) -> str:
    """Return a stable content-derived hash of a node's members.

    Leaf members sign over their sections' CONTENT HASHES, not section ids, so
    the signature survives a re-split that re-mints section ids for unchanged
    content (#068) — this is what lets #064's brief skip actually fire through a
    rebuild. Upper members sign over their child node ids (stable once the level
    below is). Tokens are prefixed so a content hash and node id never collide.
    """
    content_hashes = [
        row["content_hash"]
        for row in conn.execute(
            "SELECT s.content_hash AS content_hash FROM node_members m "
            "JOIN sections s ON s.id = m.section_id WHERE m.node_id = ? "
            "ORDER BY s.content_hash",
            (node_id,),
        ).fetchall()
    ]
    if content_hashes:
        tokens = [f"c{h}" for h in sorted(content_hashes)]
    else:
        children = [
            int(row["child_id"])
            for row in conn.execute(
                "SELECT child_id FROM node_children WHERE parent_id = ? "
                "ORDER BY child_id",
                (node_id,),
            ).fetchall()
        ]
        tokens = [f"n{i}" for i in children]
    return hashlib.sha256(",".join(tokens).encode("utf-8")).hexdigest()


def _is_fresh(
    row: sqlite3.Row,
    member_sig: str,
    prompt_hash: str,
    model_name: str,
) -> bool:
    return (
        not row["stale"]
        and row["member_signature"] == member_sig
        and row["prompt_hash"] == prompt_hash
        and row["model_name"] == model_name
    )


def stale_or_missing(
    conn: sqlite3.Connection,
    tree: str,
    level: int,
    prompt_hash: str,
    model_name: str,
) -> tuple[int, ...]:
    """Return ids of nodes at (tree, level) needing a (re)brief.

    A node needs work when it has no brief, or when its brief is stale — its
    member set changed, or the resolved prompt template hash / model no longer
    match the provenance it was written with.
    """
    node_ids = [
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ? AND level = ? ORDER BY id",
            (tree, level),
        ).fetchall()
    ]
    result: list[int] = []
    for node_id in node_ids:
        row = get(conn, node_id)
        if row is None or not _is_fresh(
            row, member_signature(conn, node_id), prompt_hash, model_name
        ):
            result.append(node_id)
    return tuple(result)


def counts(
    conn: sqlite3.Connection,
    tree: str,
    level: int,
    prompt_hash: str,
    model_name: str,
) -> tuple[int, int]:
    """Return (fresh, stale) over the existing briefs at (tree, level)."""
    fresh = stale = 0
    rows = conn.execute(
        "SELECT b.node_id AS id FROM briefs b JOIN nodes n ON n.id = b.node_id "
        "WHERE n.tree = ? AND n.level = ?",
        (tree, level),
    ).fetchall()
    for row in rows:
        node_id = int(row["id"])
        brief = get(conn, node_id)
        assert brief is not None
        if _is_fresh(
            brief, member_signature(conn, node_id), prompt_hash, model_name
        ):
            fresh += 1
        else:
            stale += 1
    return fresh, stale


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


def child_briefs(conn: sqlite3.Connection, node_id: int) -> tuple[str, ...]:
    """Return the brief texts of an upper node's child nodes (reduce input)."""
    rows = conn.execute(
        "SELECT b.text AS text FROM node_children c "
        "JOIN briefs b ON b.node_id = c.child_id WHERE c.parent_id = ? "
        "ORDER BY c.child_id",
        (node_id,),
    ).fetchall()
    return tuple(row["text"] for row in rows)


def child_ids(conn: sqlite3.Connection, node_id: int) -> tuple[int, ...]:
    """Return an upper node's child node ids (the mechanical references)."""
    rows = conn.execute(
        "SELECT child_id FROM node_children WHERE parent_id = ? "
        "ORDER BY child_id",
        (node_id,),
    ).fetchall()
    return tuple(int(row["child_id"]) for row in rows)


def upsert(
    conn: sqlite3.Connection,
    node_id: int,
    text: str,
    *,
    model_name: str,
    prompt_name: str,
    prompt_hash: str,
    member_signature: str,
    input_tokens: int,
    output_tokens: int,
    unfaithful: str = "[]",
    flagged: str = "",
    members: str = "[]",
) -> None:
    """Store one node's brief with its provenance and member signature.

    ``unfaithful`` is the faithfulness gate's JSON verdict (#063); default '[]'
    keeps callers that do not run the gate unchanged. ``flagged`` is the shape
    guard's reason (#103) — empty when the reply looked like a brief.
    ``members`` is the JSON list of member URIs (or child node ids) the brief
    covers: data ABOUT the brief, kept out of its text so #071's passages carry
    prose only (#102), and re-attached by the export renderer.
    """
    conn.execute(
        "INSERT OR REPLACE INTO briefs(node_id, text, model_name, prompt_name, "
        "prompt_hash, member_signature, input_tokens, output_tokens, "
        "unfaithful, flagged, members, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            node_id,
            text,
            model_name,
            prompt_name,
            prompt_hash,
            member_signature,
            input_tokens,
            output_tokens,
            unfaithful,
            flagged,
            members,
            _now(),
        ),
    )


def get(conn: sqlite3.Connection, node_id: int) -> sqlite3.Row | None:
    """Return a node's brief row, or None."""
    return conn.execute(
        "SELECT node_id, text, model_name, prompt_name, prompt_hash, "
        "member_signature, input_tokens, output_tokens, unfaithful, flagged, "
        "members, stale, judged_signature FROM briefs WHERE node_id = ?",
        (node_id,),
    ).fetchone()


def mark_stale(conn: sqlite3.Connection, node_id: int) -> None:
    """Flag a node's brief for regeneration without touching its members (#087).

    A sticky-placed leaf keeps its id so #068's ancestor signature is unchanged;
    propagate sets this so the next brief pass regenerates the ancestor anyway.
    """
    conn.execute("UPDATE briefs SET stale = 1 WHERE node_id = ?", (node_id,))


def mark_judged(conn: sqlite3.Connection, node_id: int, signature: str) -> None:
    """Record the member set propagate judged this brief against (#110).

    Separate from ``member_signature`` on purpose: that one drives #064's
    re-brief skip, and a judged marker written there would suppress a genuine
    regeneration. A re-brief clears this (``upsert`` does not list the column),
    because a new brief has not been judged.
    """
    conn.execute(
        "UPDATE briefs SET judged_signature = ? WHERE node_id = ?",
        (signature, node_id),
    )


def unfaithful_count(conn: sqlite3.Connection, tree: str, level: int) -> int:
    """Return how many briefs at (tree, level) the gate flagged (for health)."""
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM briefs b JOIN nodes n ON n.id = b.node_id "
            "WHERE n.tree = ? AND n.level = ? AND b.unfaithful != '[]'",
            (tree, level),
        ).fetchone()[0]
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
