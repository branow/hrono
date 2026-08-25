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


def scores(
    conn: sqlite3.Connection,
    query_vec: Sequence[float],
    model_name: str,
) -> dict[int, float]:
    """Return the vector z-score for EVERY embedded passage (support map).

    The keyword leg (#073) needs a passage's vector z even when it is below the
    3.5 qualify floor (its support bar is 3.0), and the endpoint (#074) fuses on
    it, so the full z-map is exposed here and ``search`` just filters it.
    """
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
        return {}

    raw = [score for _, score in scored]
    mean = sum(raw) / len(raw)
    std = math.sqrt(sum((s - mean) ** 2 for s in raw) / len(raw))
    if std == 0.0:
        return {passage_id: 0.0 for passage_id, _ in scored}
    return {passage_id: (score - mean) / std for passage_id, score in scored}


def search(
    conn: sqlite3.Connection,
    query_vec: Sequence[float],
    model_name: str,
) -> tuple[tuple[int, float], ...]:
    """Return (passage_id, z) for passages clearing z >= 3.5, best first."""
    qualified = [
        (passage_id, z)
        for passage_id, z in scores(conn, query_vec, model_name).items()
        if z >= Z_FLOOR
    ]
    return tuple(sorted(qualified, key=lambda hit: hit[1], reverse=True))


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))
