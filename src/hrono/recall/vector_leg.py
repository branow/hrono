"""Recall's vector leg (T26.1): path-blended similarity, z-scored and floored.

Scores every embedded passage (source #069 and brief #071) by the a=0.5
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

TWO VIEWS, BEST OF EITHER (#127). The blend above is the CLUSTERING vector, and
half a passage's norm there is its file path — which a question phrased in
ordinary English shares no vocabulary with, so the content signal is halved and
dragged toward the median. Measured on the QA corpus, "how do I style terminal
output with colours" over a corpus containing the whole of chalk: ONE passage
cleared the floor blended, SEVENTEEN content-only. But dropping the blend is not
the fix either — "generate a version 7 uuid" went 10 hits to 1, because THAT
question's vocabulary lives in the path (`uuid/version7.go`). The two question
shapes pull opposite ways, so a passage is scored in BOTH spaces, each z-scored
against its own distribution, and keeps the better of the two: evidence that a
passage is about the question can come from what it says or from where it lives,
and requiring both halves at once was the defect. Measured, the union dominates
— every question tested is at least as good as blended, and the eleven absent
questions are unchanged at zero.

``Z_FLOOR`` is 3.2, swept not guessed (#134). #127 left two paraphrases failing
with the RIGHT documents ranked #1-5 at z=3.19-3.62, and the suspicion was that
corroboration was the binding constraint. The sweep says otherwise. Relaxing
corroboration is the wrong lever and leaks badly — dropping ``KEYWORD_SUPPORT``
to -1.0 takes the eleven absent questions from 1 answered to 5, and lowering
``UNCORROBORATED_FLOOR`` takes it to 2. Lowering the CORROBORATED floor leaks
nothing: corroboration still gates, the bar simply sits where the evidence puts
it.

    Z_FLOOR  UNCORROB  KW_SUPPORT | paraphrases | corpus-vocab | absent answered
       3.5       4.5         0.0  |     4/6     |     5/5      |   1/11 (was)
       3.2       4.5         0.0  |     6/6     |     5/5      |   1/11 (is)
       3.0       4.5         0.0  |     6/6     |     5/5      |   1/11

3.0 works too, so 3.2 is not a cliff edge — it is the smaller move with headroom
below it. The one absent question that answers is "sourdough starter hydration"
at a single hit, and it did that before this change as well.

REJECTED, with numbers: letting a BRIEF passage corroborate a source hit under
the same topic. Briefs describe topics conceptually, so they looked like the
natural corroborator for a conceptually-phrased question. Measured, a brief
passage cleared z 3.5 for ONE of twenty-two questions — a summary competes
against source passages in the same distribution and loses — so the rule had
nothing to fire on and changed not one result on any suite.

The statistic is unchanged on purpose. An absolute cosine floor reads better on
one corpus but is model-specific and would need recalibrating whenever the
embedding model changes; the z-score is scale-free and portable, so ``Z_FLOOR``
stays a baked constant with no per-model tuning.
"""

from __future__ import annotations

import json
import math
import sqlite3
from array import array
from collections.abc import Sequence

import numpy

from hrono.cluster.blend import path_body, similarity_weights
from hrono.ingest.identity import content_hash

Z_FLOOR = 3.2  # with keyword corroboration (#134; was 3.5)
UNCORROBORATED_FLOOR = 4.5  # without it (#102): derived on the QA corpus
KEYWORD_SUPPORT = 0.0  # keyword z that counts as corroboration
_NO_SUPPORT = -1.0  # a passage the question's terms never matched
_MAD_TO_SD = 1.4826  # MAD -> sd-equivalent for a normal distribution


def scores(
    conn: sqlite3.Connection,
    query_vec: Sequence[float],
    model_name: str,
    scope: frozenset[int] | None = None,
) -> dict[int, float]:
    """Return the vector z-score for every embedded passage IN SCOPE.

    The keyword leg (#073) needs a passage's vector z even when it is below the
    qualify floor (its support bar is 3.0), and the endpoint (#074) fuses on
    it, so the full z-map is exposed here and ``search`` just filters it.

    ``scope`` is the tree's passages, or None for every one of them (#166). It
    is applied before the z, not after: a passage's z is measured against the
    passages that could have answered the question, which is its tree's.

    THE ARITHMETIC IS THE COST, and it is done in numpy (#194). Measured at 384
    dims: 0.15 ms per passage per query in interpreted loops, 18x faster as two
    matrix-vector products — 1.215s to 0.066s over 8000 passages (#193). The
    math is unchanged: the same two views, over the same population, with the
    same weights, read from `blend.blend_weights` rather than re-derived. What
    an ANN index would change instead is WHICH passages are scored, and the z
    is taken over the query's own full distribution, so that is a question
    about the recipe and this is not (#077).
    """
    content_weight, path_weight = similarity_weights()
    bodies, paths, ids = _stack(conn, model_name, scope)
    if not ids:
        return {}

    query = _unit_row(numpy.asarray(query_vec, dtype=numpy.float64))
    content_sim = bodies @ query
    # `combined_vector` is concat(cw * unit(content), pw * unit(path)) and the
    # query enters `combine(q, q)` the same way, so their dot product is this
    # (#039) — one product per view instead of a 768-wide one per passage.
    blended = content_weight * content_sim + path_weight * (paths @ query)

    by_blend = _z_scores(list(zip(ids, blended.tolist(), strict=True)))
    by_content = _z_scores(list(zip(ids, content_sim.tolist(), strict=True)))
    return {
        passage_id: max(z, by_content.get(passage_id, z))
        for passage_id, z in by_blend.items()
    }


def _stack(
    conn: sqlite3.Connection,
    model_name: str,
    scope: frozenset[int] | None,
) -> tuple[numpy.ndarray, numpy.ndarray, list[int]]:
    """The in-scope passages' unit content and path vectors, as two matrices.

    A passage missing either vector is skipped, exactly as scoring it one at a
    time did: half a blend is not a smaller score, it is a different question.

    Scope is applied in the passage SELECT and the vectors are read for the
    surviving hashes only: this used to read the WHOLE embeddings table per
    query — every orphan row, every other tree's vectors — so query cost grew
    with the database, not the tree asked.
    """
    rows = _passages(conn, scope)
    needed = {str(row["content_hash"]) for row in rows} | {
        content_hash(path_body(str(row["path"]))) for row in rows
    }
    vectors = _vectors(conn, model_name, needed)
    ids: list[int] = []
    bodies: list[numpy.ndarray] = []
    paths: list[numpy.ndarray] = []
    for row in rows:
        body = vectors.get(str(row["content_hash"]))
        path = vectors.get(content_hash(path_body(str(row["path"]))))
        if body is None or path is None:
            continue
        ids.append(int(row["id"]))
        bodies.append(body)
        paths.append(path)
    if not ids:
        empty = numpy.zeros((0, 0))
        return empty, empty, []
    return (
        _unit_rows(numpy.vstack(bodies)),
        _unit_rows(numpy.vstack(paths)),
        ids,
    )


def _passages(
    conn: sqlite3.Connection, scope: frozenset[int] | None
) -> list[sqlite3.Row]:
    if scope is None:
        return conn.execute(
            "SELECT id, content_hash, path FROM passages ORDER BY id"
        ).fetchall()
    return conn.execute(
        "SELECT id, content_hash, path FROM passages "
        "WHERE id IN (SELECT value FROM json_each(?)) ORDER BY id",
        (json.dumps(sorted(scope)),),
    ).fetchall()


def _vectors(
    conn: sqlite3.Connection, model_name: str, needed: set[str]
) -> dict[str, numpy.ndarray]:
    """The needed hashes' stored vectors for this model, by content hash."""
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


def _unit_rows(matrix: numpy.ndarray) -> numpy.ndarray:
    """Row-wise unit length, leaving a zero row as zeros (`blend.unit`)."""
    norms = numpy.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / numpy.where(norms == 0.0, 1.0, norms)


def _unit_row(vector: numpy.ndarray) -> numpy.ndarray:
    norm = float(numpy.linalg.norm(vector))
    return vector if norm == 0.0 else vector / norm


def _z_scores(scored: Sequence[tuple[int, float]]) -> dict[int, float]:
    """z against the distribution's own median and MAD (#102)."""
    raw = [score for _, score in scored]
    centre = _median(raw)
    spread = _spread(raw, centre)
    if spread == 0.0:
        return {passage_id: 0.0 for passage_id, _ in scored}
    return {
        passage_id: (score - centre) / spread for passage_id, score in scored
    }


def qualify(
    vector_z: dict[int, float],
    keyword_z: dict[int, float],
) -> tuple[tuple[int, float], ...]:
    """Return (passage_id, z) for passages that qualify, best first.

    Two bars, because similarity alone cannot tell "about this" from "nearest
    of the available topics" (#102). A passage the question's own terms
    corroborate — keyword z at or above ``KEYWORD_SUPPORT``, the average of
    everything the query matched at all — qualifies at ``Z_FLOOR``. One no term
    supports has to clear ``UNCORROBORATED_FLOOR``.

    This is #073's rule applied symmetrically: a keyword hit already needs
    vector support at z >= 3.0 because BM25's background is stopword matches,
    and the mirror is that an embedding's nearest neighbours are never empty —
    ask a corpus about labrador puppies and it still has a most-similar passage.
    The keyword leg is the orthogonal evidence: measured on the QA corpus, the
    absent question's five vector candidates carried no distinctive term of it
    (its one FTS match scored keyword z -0.37, i.e. matched on stopwords), while
    the on-topic questions' candidates carried uuid/v7/NewV7 and signer/unsign.

    Accepted cost, deliberately: a question phrased in vocabulary the corpus
    does not share is cut and fails safe to the explore message. Better to cut
    than to leak — a confident wrong answer is what recall exists to avoid.
    """
    qualified = [
        (passage_id, z)
        for passage_id, z in vector_z.items()
        if z >= UNCORROBORATED_FLOOR
        or (
            z >= Z_FLOOR
            and keyword_z.get(passage_id, _NO_SUPPORT) >= KEYWORD_SUPPORT
        )
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
