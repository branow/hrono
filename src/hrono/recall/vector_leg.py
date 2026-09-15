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

The z-score is taken against the distribution's MEDIAN and MAD, not its mean and
standard deviation (#102). Mean/sd are estimated from the same population being
scored, so the matches inflate the baseline they are then measured against —
worst exactly when the corpus is ON-TOPIC. Measured on the QA corpus: "generate
a version 7 uuid" gave mean 0.178 / sd 0.161, so genuine matches at cosine
0.71/0.70/0.67 scored z = 3.27/3.22/3.06 and were cut, while 23 passages in the
corpus matched the question — 2 hits cleared the floor. Against a flat off-topic
population (mean 0.007 / sd 0.050) a mediocre 0.20 nearly cleared it. The
matches live in the TAIL, so estimating the noise floor from the BODY of the
distribution stops them raising their own threshold: same corpus, same probe,
2 -> 53 hits on-topic and 1 -> 1 off-topic. MAD collapses to zero when more than
half the population shares one score, so the spread falls back to the standard
deviation there (see ``_spread``) rather than scoring everything zero.

The statistic is unchanged on purpose. An absolute cosine floor reads better on
one corpus but is model-specific and would need recalibrating whenever the
embedding model changes; the z-score is scale-free and portable, so ``Z_FLOOR``
stays baked at 3.5 with no per-model constants.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Sequence

from hrono.cluster.blend import combine, combined_vector

Z_FLOOR = 3.5
_MAD_TO_SD = 1.4826  # MAD -> sd-equivalent for a normal distribution


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
    centre = _median(raw)
    spread = _spread(raw, centre)
    if spread == 0.0:
        return {passage_id: 0.0 for passage_id, _ in scored}
    return {
        passage_id: (score - centre) / spread for passage_id, score in scored
    }


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


def _spread(raw: Sequence[float], centre: float) -> float:
    """The MAD as an sd-equivalent, falling back to the sd when it collapses.

    MAD is zero whenever MORE THAN HALF the population shares one score — a
    handful of identical passages, or a corpus small enough that the body is a
    single value. There is still a scale to measure against in that case, so
    the fallback is the standard deviation; only a population with no spread at
    all scores everything zero.
    """
    mad = _median([abs(score - centre) for score in raw]) * _MAD_TO_SD
    if mad > 0.0:
        return mad
    mean = sum(raw) / len(raw)
    return math.sqrt(sum((score - mean) ** 2 for score in raw) / len(raw))


def _median(values: Sequence[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))
