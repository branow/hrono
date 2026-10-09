"""Persist and read back ingested sections, passages, and content bodies.

Bodies are content-addressed: one ``contents`` row per unique hash, so
re-storing identical bytes is a no-op and every body is embedded once. Sections
and passages hold identity (the four address parts + rendered URI) and byte
ranges as data; a passage points at its parent section, and both point at a body
by hash. All access goes through the caller's connection (held under the
Database lock). Replacing a source's rows is delete-by-source (passages cascade)
then insert, so a re-split is idempotent.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime

from hrono.ingest.identity import Address


def upsert_content(
    conn: sqlite3.Connection, content_hash: str, body: bytes
) -> None:
    """Store a body once, keyed by its hash; a repeat hash is a no-op."""
    conn.execute(
        "INSERT OR IGNORE INTO contents(content_hash, body, byte_len, "
        "created_at) VALUES (?, ?, ?, ?)",
        (content_hash, body, len(body), _now()),
    )


def clear_source(conn: sqlite3.Connection, source: str) -> None:
    """Drop a source's sections (passages cascade); bodies are left shared."""
    conn.execute("DELETE FROM sections WHERE source = ?", (source,))


def insert_section(
    conn: sqlite3.Connection,
    *,
    source: str,
    address: Address,
    start: int,
    end: int,
    content_hash: str,
    ordinal: int,
) -> int:
    """Insert one section; return its new id."""
    cursor = conn.execute(
        "INSERT INTO sections(source, source_type, instance, path, version, "
        "uri, byte_start, byte_end, content_hash, ordinal, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            source,
            address.source_type,
            address.instance,
            address.path,
            address.version,
            address.uri,
            start,
            end,
            content_hash,
            ordinal,
            _now(),
        ),
    )
    return int(cursor.lastrowid or 0)


def insert_passage(
    conn: sqlite3.Connection,
    *,
    section_id: int,
    source: str,
    address: Address,
    start: int,
    end: int,
    content_hash: str,
    sp_paths: tuple[str, ...],
    ordinal: int,
) -> int:
    """Insert one passage under its section; return its new id."""
    cursor = conn.execute(
        "INSERT INTO passages(section_id, source, source_type, instance, path, "
        "version, uri, byte_start, byte_end, content_hash, sp_paths, ordinal, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            section_id,
            source,
            address.source_type,
            address.instance,
            address.path,
            address.version,
            address.uri,
            start,
            end,
            content_hash,
            json.dumps(list(sp_paths)),
            ordinal,
            _now(),
        ),
    )
    return int(cursor.lastrowid or 0)


def get_content(conn: sqlite3.Connection, content_hash: str) -> bytes | None:
    """Return a stored body by hash, or None."""
    row = conn.execute(
        "SELECT body FROM contents WHERE content_hash = ?", (content_hash,)
    ).fetchone()
    return bytes(row["body"]) if row is not None else None


def content_count(conn: sqlite3.Connection) -> int:
    """Return how many distinct bodies are stored (for dedup assertions)."""
    return int(conn.execute("SELECT COUNT(*) FROM contents").fetchone()[0])


def list_sections(
    conn: sqlite3.Connection, source: str
) -> tuple[sqlite3.Row, ...]:
    """Return a source's sections in stored order."""
    rows = conn.execute(
        "SELECT * FROM sections WHERE source = ? ORDER BY ordinal, id",
        (source,),
    ).fetchall()
    return tuple(rows)


def section_by_uri(
    conn: sqlite3.Connection, uri: str
) -> tuple[sqlite3.Row, ...]:
    """Return the sections at ``uri`` (byte range distinguishes them)."""
    rows = conn.execute(
        "SELECT * FROM sections WHERE uri = ? ORDER BY ordinal, id", (uri,)
    ).fetchall()
    return tuple(rows)


def list_passages(
    conn: sqlite3.Connection, section_id: int
) -> tuple[sqlite3.Row, ...]:
    """Return a section's passages in stored order."""
    rows = conn.execute(
        "SELECT * FROM passages WHERE section_id = ? ORDER BY ordinal, id",
        (section_id,),
    ).fetchall()
    return tuple(rows)


def _now() -> str:
    return datetime.now(UTC).isoformat()
