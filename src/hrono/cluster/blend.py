"""Path-blended clustering vectors: what a section says plus where it lives.

Content similarity alone clusters unrelated files that share vocabulary, so the
file path is folded in. The combined vector is the scaled concatenation

    combined = [ sqrt(1 - ALPHA) * content_unit , sqrt(ALPHA) * path_unit ]

so a plain dot product of two combined vectors is exactly
``(1 - ALPHA) * content_similarity + ALPHA * path_similarity`` — path-aware
similarity that standard UMAP/ANN tooling recovers unchanged. ``ALPHA`` is a
baked constant (0.5), not config.

The path is embedded with the SAME model as content, embed-once: its string is
registered as a content body (keyed by hash), so #035's store + embed op
vectorise it exactly once. The combined vector is computed on the fly from the
two stored component vectors (storage stays lean); the components are assumed
non-unit and are L2-normalised here so the similarity identity holds.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Iterable, Sequence

from hrono.embed.store import get_vector
from hrono.ingest.identity import content_hash
from hrono.ingest.store import upsert_content

ALPHA = 0.5


def combine(
    content_vec: Sequence[float],
    path_vec: Sequence[float],
    alpha: float = ALPHA,
) -> tuple[float, ...]:
    """Blend a content and path vector into one path-aware clustering vector."""
    content_unit = _unit(content_vec)
    path_unit = _unit(path_vec)
    content_weight = math.sqrt(1 - alpha)
    path_weight = math.sqrt(alpha)
    return tuple(
        [content_weight * value for value in content_unit]
        + [path_weight * value for value in path_unit]
    )


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


def combined_vector(
    conn: sqlite3.Connection,
    content_digest: str,
    path: str,
    model_name: str,
) -> tuple[float, ...] | None:
    """Return a section's combined vector, or None if a component is missing."""
    content = get_vector(conn, content_digest, model_name)
    path_component = get_vector(conn, content_hash(path_body(path)), model_name)
    if content is None or path_component is None:
        return None
    return combine(content, path_component)


def _unit(vec: Sequence[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(value * value for value in vec))
    if norm == 0.0:
        return tuple(vec)
    return tuple(value / norm for value in vec)
