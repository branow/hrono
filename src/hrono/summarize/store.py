"""Persist and read back per-section condensations, keyed (content_hash, model).

``pending`` drives the incremental skip exactly like the embeddings store: it
returns the distinct SECTION content hashes (bodies, not passages or paths) that
have no condensation for the target model yet, so a re-run condenses nothing and
a model swap re-condenses under the new key. ``upsert`` stores one condensation
once; a repeat key is a no-op.

A section the model REFUSED (``refuse``) is held back from ``pending`` while the
request is the same one it refused: a refusal is never cached as a
condensation, so without the record every sync would pay two calls to be
refused again, forever. ``request_for`` is what "the same request" means.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime

from hrono.ingest.identity import content_hash as digest
from hrono.ingest.store import upsert_content
from hrono.summarize.resolve import model_fingerprint, template_hash
from hrono.summarize.shape import talks_back


def pending(
    conn: sqlite3.Connection,
    model_name: str,
    *,
    request: str | None = None,
    sources: tuple[str, ...] | None = None,
) -> tuple[tuple[str, bytes], ...]:
    """Return (content_hash, body) for sections not yet condensed for a model.

    Distinct section content hashes only — passage and path bodies never
    condense. A stored condensation that is the model talking back counts as
    MISSING: cached by content hash it would stay forever, and every brief over
    that section would read it as source. A section already refused for
    ``request`` is left out; with no ``request``, refusals are not consulted.

    ``sources`` scopes the selection to one tree's sections: condense runs as a
    stage of one tree's sync or maintain, and an unscoped SELECT would make that
    run pay LLM calls for every other tree's pending sections too — spend the
    operator asked for on no tree at all. None keeps the whole-corpus read for
    an unscoped database.

    Bodies are read only for what is pending. Condense runs on every sync, and
    reading every section body to find the few that changed would make an
    unchanged tree cost its whole corpus in I/O. The selection is set-based and
    binds a fixed number of parameters whatever the corpus size: one bound
    parameter per pending hash fails outright past SQLite's 32,766-variable
    limit, which is every first build of a large corpus.
    """
    redo = sorted({digest for digest, _, _ in unusable(conn, model_name)})
    scoped = (
        ""
        if sources is None
        else "AND s.source IN (SELECT value FROM json_each(?)) "
    )
    rows = conn.execute(
        "SELECT DISTINCT s.content_hash AS h, c.body AS body FROM sections s "
        "JOIN contents c ON c.content_hash = s.content_hash "
        f"WHERE s.source_type != 'node' {scoped}"  # noqa: S608
        "AND (NOT EXISTS (SELECT 1 FROM "
        "condensations d WHERE d.content_hash = s.content_hash "
        "AND d.model_name = ?) OR s.content_hash IN "
        "(SELECT value FROM json_each(?))) AND NOT EXISTS (SELECT 1 FROM "
        "condense_refusals r WHERE r.content_hash = s.content_hash "
        "AND r.model_name = ? AND r.request = ?) ORDER BY s.content_hash",
        (
            *(() if sources is None else (json.dumps(list(sources)),)),
            model_name,
            json.dumps(redo),
            model_name,
            request,
        ),
    ).fetchall()
    return tuple((row["h"], bytes(row["body"])) for row in rows)


def paths(conn: sqlite3.Connection, digests: list[str]) -> dict[str, str]:
    """A file path for each content hash: the first, when several files hold
    the same bytes (a condensation is shared by content)."""
    rows = conn.execute(
        "SELECT content_hash AS h, MIN(path) AS path FROM sections "
        "WHERE content_hash IN (SELECT value FROM json_each(?)) "
        "GROUP BY content_hash",
        (json.dumps(digests),),
    ).fetchall()
    return {row["h"]: row["path"] for row in rows}


def redo(
    conn: sqlite3.Connection, model_name: str, request: str
) -> tuple[str, ...]:
    """Hashes whose condensation is not one and that ``request`` may retry.

    What makes a sync over an unchanged corpus run condense at all: a
    talk-back not yet refused for this request. Once it is, the sync leaves it
    alone until the body, the model or the prompt changes.
    """
    held = {
        row["content_hash"]
        for row in conn.execute(
            "SELECT content_hash FROM condense_refusals "
            "WHERE model_name = ? AND request = ?",
            (model_name, request),
        )
    }
    return tuple(
        digest
        for digest, _, _ in unusable(conn, model_name)
        if digest not in held
    )


def unusable(
    conn: sqlite3.Connection, model_name: str
) -> tuple[tuple[str, str, str], ...]:
    """Condensations that are not ones: (hash, why, text).

    Every stored condensation the current gate fails, and every section the
    model refused with nothing stored for it — that one has no row in
    ``condensations`` to fail, and without the refusal it would leave the
    operator's list while still uncondensed.
    """
    rows = conn.execute(
        "SELECT content_hash, text FROM condensations WHERE model_name = ? "
        "ORDER BY content_hash",
        (model_name,),
    ).fetchall()
    stored = tuple(
        (row["content_hash"], why, row["text"])
        for row in rows
        if (why := talks_back(row["text"]))
    )
    refused = conn.execute(
        "SELECT r.content_hash, r.reason, r.text FROM condense_refusals r "
        "WHERE r.model_name = ? AND NOT EXISTS (SELECT 1 FROM condensations "
        "d WHERE d.content_hash = r.content_hash AND d.model_name = ?) "
        "ORDER BY r.content_hash",
        (model_name, model_name),
    ).fetchall()
    return stored + tuple(
        (row["content_hash"], row["reason"], row["text"]) for row in refused
    )


def request_for(model: Mapping[str, object], template: str) -> str:
    """What a refusal was refused FOR: the model's words and the prompt.

    The model fingerprint rather than its name, so repointing a name
    at another upstream model is a new request; the template hash, so an
    edited prompt is one too.
    """
    material = f"{model_fingerprint(model)}:{template_hash(template)}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def refuse(
    conn: sqlite3.Connection,
    content_hash: str,
    model_name: str,
    request: str,
    reason: str,
    text: str,
) -> None:
    """Record that ``request`` was refused for a section, over any older."""
    conn.execute(
        "INSERT OR REPLACE INTO condense_refusals(content_hash, model_name, "
        "request, reason, text, refused_at) VALUES (?, ?, ?, ?, ?, ?)",
        (content_hash, model_name, request, reason, text, _now()),
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
    brief pass rewrites exactly the briefs that read the bad text.
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
    """Store one condensation; a repeat (hash, model) key is a no-op.

    Its text is also stored as a content body, so the embed op vectorises it
    once: clustering reads a section by its condensation's vector.
    """
    conn.execute(
        "INSERT OR IGNORE INTO condensations(content_hash, model_name, text, "
        "input_tokens, output_tokens, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (content_hash, model_name, text, input_tokens, output_tokens, _now()),
    )
    body = text.encode("utf-8")
    upsert_content(conn, digest(body), body)


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
