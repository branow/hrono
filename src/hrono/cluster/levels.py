"""The ``cluster-briefs`` op: build the next tree level up from a level's brief.

The tree is recursive — cluster -> brief -> embed briefs -> cluster the briefs
-> ... to root — so this reuses the SAME embed (#035) and cluster build (#040)
over BRIEF TEXT instead of leaf sections, proving the pipeline is level-agnostic
not section-only. For a source level N: register each level-N node's brief text
as embeddable content (embed-once by content hash), run the #035 embed op to
vectorise it, then cluster the brief vectors with the #040 build (same baked
constants) and persist level N+1 nodes whose members are the level-N node ids
(via node_children).

Path-blend (#039) is content-ONLY for briefs: a topic has no file path, so there
is nothing to blend (how-hrono-works.md) — the clustering vector is the brief's
L2-normalised content vector (alpha = 0), not a combined one, and no synthetic
path is invented. Heavy compute runs outside the #008 lock like #040.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence

from hrono.cluster import ClusterError, store
from hrono.embed.model import resolve_embedding_model
from hrono.embed.op import embed
from hrono.embed.store import get_vector
from hrono.ingest.identity import content_hash
from hrono.ingest.store import upsert_content
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.summarize import briefs

Builder = Callable[..., object]


def cluster_briefs(
    job: Job,
    context: JobContext,
    *,
    build: Builder | None = None,
    encoder_for: object | None = None,
) -> None:
    """Cluster a level's briefs into the next level up (members = node ids)."""
    builder = build if build is not None else _load_builder()
    tree = job.tree or "default"
    source_level = _source_level(job.scope)

    with context.database.connect() as conn:
        node_briefs = briefs.level_briefs(conn, tree, source_level)
    if not node_briefs:
        return

    with context.database.connect() as conn, conn:
        for _, text in node_briefs:
            body = text.encode("utf-8")
            upsert_content(conn, content_hash(body), body)

    embed(job, context, encoder_for=encoder_for)

    with context.database.connect() as conn:
        model_name = str(resolve_embedding_model(conn, job.scope)["name"])
        pairs = [
            (node_id, get_vector(conn, content_hash(text.encode()), model_name))
            for node_id, text in node_briefs
        ]
    ready = [(node_id, vec) for node_id, vec in pairs if vec is not None]
    if not ready:
        return

    child_ids = [node_id for node_id, _ in ready]
    vectors = [_unit(vec) for _, vec in ready]
    result = builder(vectors, init=None)

    members = [
        (label, child_ids[i], result.attached[i], sim)
        for i, (label, sim) in enumerate(
            zip(result.labels, result.assignment_similarity, strict=True)
        )
    ]
    with context.database.connect() as conn, conn:
        store.replace_level(conn, tree, source_level + 1, members)


def _source_level(scope: dict[str, object]) -> int:
    level = scope.get("level")
    return int(level) if isinstance(level, int) else 0


def _unit(vec: Sequence[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(value * value for value in vec))
    if norm == 0.0:
        return tuple(vec)
    return tuple(value / norm for value in vec)


def _load_builder() -> Builder:
    try:
        from hrono.cluster.build import build_clusters
    except ImportError as exc:
        raise ClusterError("clustering backend is not installed") from exc
    return build_clusters


OPS["cluster-briefs"] = cluster_briefs
