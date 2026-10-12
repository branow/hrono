"""Clustering vectors: what a section is for plus where it lives.

Content similarity alone clusters unrelated files that share vocabulary, so
where a file lives is folded in. The clustering vector is the scaled
concatenation

    combined = [ sqrt(TEXT_WEIGHT) * text_unit , sqrt(FOLDER_WEIGHT) * folders ]

so a plain dot product of two combined vectors is exactly
``TEXT_WEIGHT * text_similarity + FOLDER_WEIGHT * folder_similarity`` —
similarity that standard UMAP/ANN tooling recovers unchanged. Both weights are
baked (0.6 and 0.4, docs/evaluations/2026-10-cluster-formula/), not config.

The text view is the embedding of the section's CONDENSATION, which opens with
what the section is for; a raw section opens with its licence and imports, and
an embedder that reads its first few hundred tokens clusters on those. A
section not condensed yet falls back to its raw content's vector. Condensations
are registered as content bodies when stored, so the embed op vectorises each
exactly once.

The folder view is ``prefix_h`` of the formula study: every leading prefix of
``source/folders/file`` counts, the one at depth d weighing 1/d, so the
repository and the service folder weigh most, deep package folders little,
and no depth is cut off. The similarity of two paths is the weight of their
shared prefixes over the geometric mean of their totals: a cosine of indicator
vectors with sqrt(1/d) per prefix. Those vectors are hashed (signed feature
hashing) into a fixed width, so nothing is stored and a new path needs no
vocabulary.

Recall and the health page's path view still blend the content with the
EMBEDDED path string (``ALPHA``, ``path_body``): that is a retrieval signal,
not the clustering one.
"""

from __future__ import annotations

import hashlib
import math
import sqlite3
import struct
from collections.abc import Iterable, Sequence

from hrono.embed.store import get_vector
from hrono.ingest.identity import content_hash
from hrono.ingest.store import upsert_content

ALPHA = 0.5  # recall's content/path-string blend

TEXT_WEIGHT = 0.6
FOLDER_WEIGHT = 0.4
FOLDER_DIMS = 2048


def combine(
    content_vec: Sequence[float],
    path_vec: Sequence[float],
    alpha: float = ALPHA,
) -> tuple[float, ...]:
    """Blend a content and path vector into one path-aware clustering vector."""
    content_unit = unit(content_vec)
    path_unit = unit(path_vec)
    content_weight, path_weight = blend_weights(alpha)
    return tuple(
        [content_weight * value for value in content_unit]
        + [path_weight * value for value in path_unit]
    )


def blend_weights(alpha: float = ALPHA) -> tuple[float, float]:
    """The (content, path) weights `combine` applies. ONE definition.

    Recall scores thousands of passages per query and does it in numpy;
    it needs these two numbers rather than the concatenated vector, and it must
    not re-derive them — `combine` above is what a passage's stored clustering
    vector means, and two places computing `sqrt(1 - alpha)` is two places to
    disagree about what alpha is.
    """
    return math.sqrt(1 - alpha), math.sqrt(alpha)


def similarity_weights(alpha: float = ALPHA) -> tuple[float, float]:
    """The weights a DOT PRODUCT of two combined vectors applies per view.

    `combine` scales each half by `sqrt(w)`, and both sides of the dot product
    carry that scaling, so each view arrives weighted by w — the SQUARE of the
    vector weight. Recall needs this form because it scores the two views
    separately instead of dotting one 768-wide vector.

    It cannot be checked against the baked ALPHA of 0.5: the two weights are
    equal there, and a z-score is invariant under scaling all scores alike, so
    squaring or not squaring gives identical rankings. The exponent only shows
    itself at an asymmetric alpha, which is where it is tested.
    """
    content_weight, path_weight = blend_weights(alpha)
    return content_weight**2, path_weight**2


def path_body(path: str) -> bytes:
    """The exact bytes embedded for a path: its repo-relative string, UTF-8."""
    return path.encode("utf-8")


def register_path_bodies(
    conn: sqlite3.Connection, paths: Iterable[str]
) -> None:
    """Store each distinct path string as a content body so it embeds once."""
    for path in set(paths):
        body = path_body(path)
        upsert_content(conn, content_hash(body), body)


def path_blend_vector(
    conn: sqlite3.Connection,
    content_digest: str,
    path: str,
    model_name: str,
) -> tuple[float, ...] | None:
    """The content blended with the embedded path string (``ALPHA``): what
    recall's vector leg scores a passage by. None if a component is missing."""
    content = get_vector(conn, content_digest, model_name)
    path_component = get_vector(conn, content_hash(path_body(path)), model_name)
    if content is None or path_component is None:
        return None
    return combine(content, path_component)


def combined_vector(
    conn: sqlite3.Connection,
    content_digest: str,
    path: str,
    model_name: str,
) -> tuple[float, ...] | None:
    """Return a section's clustering vector, or None while it has no text
    vector (neither its condensation nor its raw content is embedded)."""
    text = text_vector(conn, content_digest, model_name)
    if text is None:
        return None
    folders = folder_vector(section_source(conn, content_digest, path), path)
    return clustering_vector(text, folders)


def clustering_vector(
    text: Sequence[float], folders: Sequence[float]
) -> tuple[float, ...]:
    """Blend a text vector and a folder vector by the baked weights."""
    text_weight, folder_weight = (
        math.sqrt(TEXT_WEIGHT),
        math.sqrt(FOLDER_WEIGHT),
    )
    return tuple(
        [text_weight * value for value in unit(text)]
        + [folder_weight * value for value in unit(folders)]
    )


def text_vector(
    conn: sqlite3.Connection, content_digest: str, model_name: str
) -> tuple[float, ...] | None:
    """The vector of the section's condensation, else of its raw content."""
    condensed = condensation_text(conn, content_digest)
    if condensed is not None:
        vector = get_vector(
            conn, content_hash(condensed.encode("utf-8")), model_name
        )
        if vector is not None:
            return vector
    return get_vector(conn, content_digest, model_name)


def condensation_text(
    conn: sqlite3.Connection, content_digest: str
) -> str | None:
    """The condensation of ``content_digest`` by the condense model, if any."""
    model = condense_model(conn)
    if model is None:
        return None
    row = conn.execute(
        "SELECT text FROM condensations WHERE content_hash = ? "
        "AND model_name = ?",
        (content_digest, model),
    ).fetchone()
    return None if row is None else str(row["text"])


def condense_model(conn: sqlite3.Connection) -> str | None:
    """The name of the model the condense role resolves to, or None."""
    # Imported here: summarize depends on the cluster layer, not the reverse.
    from hrono.llm.client import LLMError
    from hrono.summarize.resolve import resolve_text_model

    try:
        return str(resolve_text_model(conn, {}, "condense")["name"])
    except LLMError:
        return None


def section_source(
    conn: sqlite3.Connection, content_digest: str, path: str
) -> str:
    """The source a section at ``path`` with these bytes belongs to.

    Two sources holding the same bytes at the same path (a root LICENSE)
    resolve to one of them; their sections are identical anyway.
    """
    row = conn.execute(
        "SELECT source FROM sections WHERE content_hash = ? AND path = ? "
        "ORDER BY id LIMIT 1",
        (content_digest, path),
    ).fetchone()
    return "" if row is None else str(row["source"])


def folder_vector(source: str, path: str) -> tuple[float, ...]:
    """The hashed prefix indicators of ``source/path``, unit length.

    Prefix d (1 = the source) carries sqrt(1/d), so the dot product of two
    such vectors is the 1/d weight of their shared prefixes over the
    geometric mean of their totals, up to hashing collisions.
    """
    segments = [source, *path.split("/")] if source else path.split("/")
    vector = [0.0] * FOLDER_DIMS
    for depth in range(1, len(segments) + 1):
        bucket, sign = _bucket("/".join(segments[:depth]))
        vector[bucket] += sign * math.sqrt(1 / depth)
    return unit(vector)


def _bucket(prefix: str) -> tuple[int, float]:
    """A stable bucket and sign for one prefix (feature hashing)."""
    digest = hashlib.blake2b(prefix.encode("utf-8"), digest_size=8).digest()
    value = struct.unpack("<Q", digest)[0]
    return value % FOLDER_DIMS, 1.0 if value >> 63 else -1.0


def unit(vec: Sequence[float]) -> tuple[float, ...]:
    """Scale a vector to unit length; a zero vector is returned as it is."""
    norm = math.sqrt(sum(value * value for value in vec))
    if norm == 0.0:
        return tuple(vec)
    return tuple(value / norm for value in vec)
