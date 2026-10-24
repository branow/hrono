"""Recall's keyword leg: the passages that share the question's words.

An FTS5 match over passage path and body, scored by BM25, for the OR of the
question's content words as stems (``gate.words``, ``gate.stem``): the same
words and the same prefix match the gate counts, so a word that lets a
question through is a word this leg can find. A name the question quotes
exactly (an identifier, a status, a queue subject) is a weak signal to an
embedding and a strong one here; fused by rank with cosine (``window``) it
lifts the passage that carries it without a floor to calibrate.
"""

from __future__ import annotations

import sqlite3

from hrono.recall import fts, gate


def ranked(
    conn: sqlite3.Connection,
    question: str,
    scope: frozenset[int] | None,
    limit: int,
) -> tuple[int, ...]:
    """The in-scope passages matching ``question``'s words, best first."""
    words = gate.words(question)
    if not words:
        return ()
    match = " OR ".join(f'"{gate.stem(word)}"*' for word in words)
    # a scope cuts hits after the fact, so read past the limit to fill it
    hits = fts.search(conn, match, limit=limit if scope is None else limit * 3)
    kept = [pid for pid, _ in hits if scope is None or pid in scope]
    return tuple(kept[:limit])
