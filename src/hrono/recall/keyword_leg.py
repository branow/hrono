"""Recall's keyword leg (T26.2): BM25 z-scored, gated by vector support.

BM25 alone is dangerous — its background distribution is stopword matches, so
meaningless text can score high — so a keyword hit NEVER qualifies alone. The
frozen recipe (how-hrono-works.md): query the FTS5 index (#070) with the
question's terms OR-ed, z-score BM25 over the MATCHED set, and qualify a passage
only at keyword z >= 6.0 AND its vector-leg z (#072) >= 3.0. Both constants are
baked.

The raw question is never passed to FTS5 MATCH (that raises on FTS5 operators or
unbalanced quotes) — it is tokenised into bare CONTENT terms (function words
dropped, #102), each quoted as a phrase and OR-ed, so an empty, all-punctuation
or all-stopword query yields no matches, not a crash.
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

# Dropped from the MATCH expression, never from the passage text: BM25's
# background is stopword matches (#073's own warning), and a question that
# overlaps a passage only on "how to a the" is not evidence about it — which is
# exactly how an absent question borrowed corroboration from a passage it had
# nothing to do with (#102). Function words only: nothing domain-specific, so
# the list needs no re-derivation for a different corpus.
_STOPWORDS = frozenset(
    (
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "but",
        "by",
        "can",
        "could",
        "do",
        "does",
        "for",
        "from",
        "has",
        "have",
        "how",
        "i",
        "if",
        "in",
        "into",
        "is",
        "it",
        "its",
        "me",
        "my",
        "of",
        "on",
        "or",
        "should",
        "so",
        "that",
        "the",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "to",
        "was",
        "we",
        "what",
        "when",
        "where",
        "which",
        "who",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
    )
)


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
    content = terms - _STOPWORDS
    if not content:
        return None
    return " OR ".join(f'"{term}"' for term in sorted(content))


def scores(conn: sqlite3.Connection, query: str) -> dict[int, float]:
    """Return the keyword z of every passage the query MATCHED at all.

    Below the leg's own 6.0 floor this is not a hit — it is lexical SUPPORT,
    the mirror of the vector z #073 already requires before a keyword hit
    counts. #102 uses it the other way round: a vector hit no term of the
    question corroborates has to clear a higher bar.
    """
    match = _match_expr(query)
    if match is None:
        return {}
    return _z(fts.search(conn, match))


def _z(hits: tuple[tuple[int, float], ...]) -> dict[int, float]:
    if not hits:
        return {}
    relevance = [(passage_id, -bm25) for passage_id, bm25 in hits]
    values = [rel for _, rel in relevance]
    mean = sum(values) / len(values)
    std = (sum((v - mean) ** 2 for v in values) / len(values)) ** 0.5
    if std == 0.0:
        # every match is equally relevant (often a single one): they are all
        # supported, none stands out. Zero is the average, which clears
        # #102's support bar and never the leg's own 6.0 floor.
        return {pid: 0.0 for pid, _ in relevance}
    return {pid: (rel - mean) / std for pid, rel in relevance}


def _qualify(
    hits: tuple[tuple[int, float], ...],
    vector_z: dict[int, float],
) -> tuple[tuple[int, float], ...]:
    qualified = [
        (passage_id, z)
        for passage_id, z in _z(hits).items()
        if z >= Z_FLOOR and vector_z.get(passage_id, 0.0) >= VECTOR_SUPPORT
    ]
    return tuple(sorted(qualified, key=lambda hit: hit[1], reverse=True))
