"""Recall's keyword leg (T26.2): BM25 z-scored, gated by vector support.

BM25 alone is dangerous — its background distribution is stopword matches, so
meaningless text can score high — so a keyword hit NEVER qualifies alone. The
frozen recipe (how-hrono-works.md): query the FTS5 index (#070) with the
question's terms OR-ed, z-score BM25 over the MATCHED set, and qualify a passage
only at keyword z >= 6.0 AND its vector-leg z (#072) >= 3.0. Both constants are
baked.

The raw question is never passed to FTS5 MATCH (that raises on FTS5 operators or
unbalanced quotes) — it is tokenised into bare terms, each quoted as a phrase
and OR-ed, so an empty or all-punctuation query yields no matches, not a crash.
BM25 is negative (more negative = better), so relevance is ``-bm25`` and higher
relevance means a higher z.
"""

from __future__ import annotations

import re
import sqlite3

from hrono.recall import fts

Z_FLOOR = 6.0
VECTOR_SUPPORT = 3.0

_TERM = re.compile(r"[A-Za-z0-9]+")


def search(
    conn: sqlite3.Connection,
    query: str,
    vector_z: dict[int, float],
) -> tuple[tuple[int, float], ...]:
    """Return (passage_id, keyword z) for passages clearing both floors."""
    match = _match_expr(query)
    if match is None:
        return ()
    return _qualify(fts.search(conn, match), vector_z)


def _match_expr(query: str) -> str | None:
    terms = {term.lower() for term in _TERM.findall(query)}
    if not terms:
        return None
    return " OR ".join(f'"{term}"' for term in sorted(terms))


def _qualify(
    hits: tuple[tuple[int, float], ...],
    vector_z: dict[int, float],
) -> tuple[tuple[int, float], ...]:
    if not hits:
        return ()
    relevance = [(passage_id, -bm25) for passage_id, bm25 in hits]
    values = [rel for _, rel in relevance]
    mean = sum(values) / len(values)
    std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
    if std == 0.0:
        return ()

    qualified = [
        (passage_id, (rel - mean) / std)
        for passage_id, rel in relevance
        if (rel - mean) / std >= Z_FLOOR
        and vector_z.get(passage_id, 0.0) >= VECTOR_SUPPORT
    ]
    return tuple(sorted(qualified, key=lambda hit: hit[1], reverse=True))
