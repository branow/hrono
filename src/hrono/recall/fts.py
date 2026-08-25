"""The FTS5 keyword index over passage path + body (T25.2).

``split`` keeps it in sync: it clears a source's rows and re-inserts them on
every re-split, so the index never drifts from the passage store and a removed
passage leaves no orphan row. ``search`` runs an FTS5 MATCH and returns each
hit's passage id with its BM25 score (FTS5's bm25 is negative — MORE negative =
better — so results come back best-first). The leg query + z-floor is #073.
"""

from __future__ import annotations

import sqlite3


def clear_source(conn: sqlite3.Connection, source: str) -> None:
    """Drop a source's FTS rows (called before a re-split repopulates them)."""
    conn.execute("DELETE FROM passages_fts WHERE source = ?", (source,))


def clear_path(conn: sqlite3.Connection, source: str, path: str) -> None:
    """Drop one path's FTS rows (an incremental re-split of that file, #085)."""
    conn.execute(
        "DELETE FROM passages_fts WHERE source = ? AND path = ?",
        (source, path),
    )


def index_passage(
    conn: sqlite3.Connection,
    *,
    passage_id: int,
    source: str,
    path: str,
    body: str,
) -> None:
    """Index one passage's path + body under its id and source."""
    conn.execute(
        "INSERT INTO passages_fts(passage_id, source, path, body) "
        "VALUES (?, ?, ?, ?)",
        (passage_id, source, path, body),
    )


def search(
    conn: sqlite3.Connection, match: str, *, limit: int = 100
) -> tuple[tuple[int, float], ...]:
    """Return (passage_id, bm25) for an FTS5 MATCH, best (lowest) first."""
    rows = conn.execute(
        "SELECT passage_id, bm25(passages_fts) AS score FROM passages_fts "
        "WHERE passages_fts MATCH ? ORDER BY score LIMIT ?",
        (match, limit),
    ).fetchall()
    return tuple((int(row["passage_id"]), float(row["score"])) for row in rows)
