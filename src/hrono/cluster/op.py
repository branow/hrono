"""The ``cluster`` job op: build a tree's bottom level from embedded sections.

Full build over a tree (empty tree = full build; incremental placement is M7):
load every embedded section's combined vector (#039) under the #008 lock,
release it, run the heavy UMAP -> HDBSCAN -> attach pipeline OUTSIDE the lock
(like #035's embedding), then re-acquire to persist the nodes, members, per-
section reduced coords, and flags. The tree is named by the job's ``tree`` (the
topic hierarchy over a corpus), defaulting to ``default``. Warm-init reads the
tree's stored coords, so a rebuild extends the prior layout; a first build inits
fresh. Reads only local vectors — no secret — so it needs no cipher. Registers
into the op registry so the worker dispatches ``cluster``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from hrono.cluster import ClusterError, store
from hrono.embed.model import resolve_embedding_model
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext

_LEVEL = 0

Builder = Callable[..., object]


def cluster(
    job: Job,
    context: JobContext,
    *,
    build: Builder | None = None,
) -> None:
    """Cluster the tree's embedded sections into bottom-level topics."""
    builder = build if build is not None else _load_builder()
    tree = job.tree or "default"
    with context.database.connect() as conn:
        config = resolve_embedding_model(conn, job.scope)
        pairs = store.section_combined_vectors(conn, str(config["name"]))
        section_ids = tuple(section_id for section_id, _ in pairs)
        init = store.stored_coords(conn, tree, section_ids)
    if not pairs:
        return

    vectors = [vector for _, vector in pairs]
    result = builder(vectors, init=init)

    members = [
        (label, section_ids[i], result.attached[i], sim)
        for i, (label, sim) in enumerate(
            zip(result.labels, result.assignment_similarity, strict=True)
        )
    ]
    coords: Sequence[tuple[int, Sequence[float]]] = [
        (section_ids[i], coord) for i, coord in enumerate(result.coords)
    ]
    with context.database.connect() as conn, conn:
        store.replace_tree(conn, tree, _LEVEL, members, coords)


def _load_builder() -> Builder:
    try:
        from hrono.cluster.build import build_clusters
    except ImportError as exc:
        raise ClusterError("clustering backend is not installed") from exc
    return build_clusters


OPS["cluster"] = cluster
