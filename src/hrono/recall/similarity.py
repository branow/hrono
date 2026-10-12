"""Recall's ranking: plain cosine of the question against every passage.

A question of several sentences is embedded sentence by sentence and each
passage takes its best one (``query.sentences``): one embedding of a long
prompt is the average of its parts, and the framing around a question (the
answer format, how to use the map) pulls it to licence headers and tests
(docs/evaluations/2026-10-recall-queries/: prompts.py).

Source passages and brief passages are ranked in one list by the cosine of
the question's embedding against the passage content's. Nothing else: the
earlier recipe blended in the embedded path string and kept only passages
whose z-score cleared a fixed floor, and on a granite tree both lost answers
plain cosine had at the top (docs/evaluations/2026-10-recall-queries/: an
answer file in the top 5 for 12 of 20 prompts with cosine, 8 with the old
recipe). Whether to answer at all is ``gate``'s question, not a score floor's.

The arithmetic is numpy: one matrix-vector product over the tree's passages.
"""

from __future__ import annotations

import json
import sqlite3
from array import array
from collections.abc import Sequence

import numpy


def ranked(
    conn: sqlite3.Connection,
    query_vec: Sequence[float] | Sequence[Sequence[float]],
    model_name: str,
    scope: frozenset[int] | None = None,
) -> tuple[tuple[int, float], ...]:
    """Every embedded passage in ``scope`` with its cosine, best first.

    ``query_vec`` is one vector, or one per sentence of the question; a
    passage then scores its best sentence. Ties break by passage id, so the
    order is deterministic.
    """
    ids, bodies = _stack(conn, model_name, scope)
    if not ids:
        return ()
    queries = numpy.atleast_2d(numpy.asarray(query_vec, dtype=numpy.float64))
    norms = numpy.linalg.norm(queries, axis=1)
    queries = queries[norms > 0.0] / norms[norms > 0.0, None]
    if len(queries) == 0:
        return ()
    cosine = (bodies @ queries.T).max(axis=1)
    order = sorted(range(len(ids)), key=lambda i: (-cosine[i], ids[i]))
    return tuple((ids[i], float(cosine[i])) for i in order)


def _stack(
    conn: sqlite3.Connection, model_name: str, scope: frozenset[int] | None
) -> tuple[list[int], numpy.ndarray]:
    """The in-scope passages' unit content vectors, as one matrix.

    Scope is applied in the passage SELECT and only those hashes' vectors are
    read: the whole embeddings table per query would make a question cost
    the database, not the tree asked. A passage with no vector is skipped.
    """
    rows = (
        conn.execute("SELECT id, content_hash FROM passages ORDER BY id")
        if scope is None
        else conn.execute(
            "SELECT id, content_hash FROM passages "
            "WHERE id IN (SELECT value FROM json_each(?)) ORDER BY id",
            (json.dumps(sorted(scope)),),
        )
    ).fetchall()
    vectors = _vectors(
        conn, model_name, {str(row["content_hash"]) for row in rows}
    )
    ids, bodies = [], []
    for row in rows:
        body = vectors.get(str(row["content_hash"]))
        if body is not None:
            ids.append(int(row["id"]))
            bodies.append(body)
    if not ids:
        return [], numpy.zeros((0, 0))
    matrix = numpy.vstack(bodies)
    norms = numpy.linalg.norm(matrix, axis=1, keepdims=True)
    return ids, matrix / numpy.where(norms == 0.0, 1.0, norms)


def _vectors(
    conn: sqlite3.Connection, model_name: str, needed: set[str]
) -> dict[str, numpy.ndarray]:
    out: dict[str, numpy.ndarray] = {}
    for row in conn.execute(
        "SELECT content_hash, vector FROM embeddings WHERE model_name = ? "
        "AND content_hash IN (SELECT value FROM json_each(?))",
        (model_name, json.dumps(sorted(needed))),
    ).fetchall():
        values = array("f")
        values.frombytes(row["vector"])
        out[str(row["content_hash"])] = numpy.asarray(
            values, dtype=numpy.float64
        )
    return out
