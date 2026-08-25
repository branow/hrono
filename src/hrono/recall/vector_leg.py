"""Recall's vector leg (T26.1): path-blended similarity, z-scored, z >= 3.5.

Scores every embedded passage (source #069 and brief #071) by the same a=0.5
path-blended similarity used for clustering — the query is content-embedded and
compared against each passage's content AND path components:

    score = (1-a)*sim(q, content) + a*sim(q, path)

which is exactly ``dot(combine(q, q), combined_vector(passage))``: putting the
query content in both blend slots recovers the blended similarity from one
dot product (#039). Raw scores are converted to z-scores over the QUERY's own
full passage distribution (not a global constant) and a passage qualifies at
z >= 3.5. Both constants are baked. Correctness first — an ANN shadow index is a
later perf concern (#035 note).
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Sequence

from hrono.cluster.blend import combine, combined_vector

Z_FLOOR = 3.5


def search(
    conn: sqlite3.Connection,
    query_vec: Sequence[float],
    model_name: str,
) -> tuple[tuple[int, float], ...]:
    """Return (passage_id, z) for passages clearing z >= 3.5, best first."""
    query = combine(query_vec, query_vec)
    scored: list[tuple[int, float]] = []
    for row in conn.execute(
        "SELECT id, content_hash, path FROM passages ORDER BY id"
    ).fetchall():
        passage = combined_vector(
            conn, row["content_hash"], row["path"], model_name
        )
        if passage is not None:
            scored.append((int(row["id"]), _dot(query, passage)))
    if not scored:
        return ()

    scores = [score for _, score in scored]
    mean = sum(scores) / len(scores)
    std = math.sqrt(sum((s - mean) ** 2 for s in scores) / len(scores))
    if std == 0.0:
        return ()

    qualified = [
        (passage_id, (score - mean) / std)
        for passage_id, score in scored
        if (score - mean) / std >= Z_FLOOR
    ]
    return tuple(sorted(qualified, key=lambda hit: hit[1], reverse=True))


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))
