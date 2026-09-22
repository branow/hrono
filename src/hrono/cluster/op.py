"""The ``cluster`` job op: build a tree's bottom level from embedded sections.

Full build over a tree (empty tree = full build; incremental placement is M7):
load every embedded section's combined vector (#039) under the #008 lock,
release it, run the heavy UMAP -> HDBSCAN -> attach pipeline OUTSIDE the lock
(like #035's embedding), then re-acquire to persist the nodes, members, per-
section reduced coords, and flags. The tree is named by the job's ``tree`` (the
topic hierarchy over a corpus), defaulting to ``default``. Warm-init reads the
tree's stored coords, so a rebuild extends the prior layout; a first build inits
fresh. A corpus below the smallest rung of the ladder (#094) cannot be reduced
at all; it is then ONE topic holding every section (#112) — the same collect
``build_tree._collect_root`` makes at the top of the tree, where "too few points
to reduce" already means "then this IS the node" rather than "then fail". A tree
of one topic is a correct, walkable map of a small repo, and recall and export
run over it unchanged. Only ``TooFewPoints`` is answered that way: the builder
raises a plain ``ClusterError`` when the reduction fails, when the clusterer
fails, when it produces no clusters and when it is not installed, and collapsing
a large corpus into one topic because its clustering BROKE would answer with a
confident, wrong map instead of failing. Every one of those still fails the
job. A full build homes every embedded section, so the incubator pool (#086) is
swept in the same transaction — its rows would
otherwise claim a re-homed chunk is still stranded. Reads only local vectors —
no secret — so it needs no cipher. Registers into the op registry so the worker
dispatches ``cluster``.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from hrono.cluster import ClusterError, TooFewPoints, incubator, store
from hrono.cluster.build import ClusterResult
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
    try:
        result = builder(vectors, init=init)
    except TooFewPoints:
        result = _one_topic(len(vectors))

    members = [
        (label, section_ids[i], result.attached[i], sim)
        for i, (label, sim) in enumerate(
            zip(result.labels, result.assignment_similarity, strict=True)
        )
    ]
    coords: Sequence[tuple[int, Sequence[float]]] = [
        (section_ids[i], coord) for i, coord in enumerate(result.coords)
    ]
    with context.database.write() as conn:
        store.replace_tree(conn, tree, _LEVEL, members, coords)
        incubator.sweep(conn, tree)


def _one_topic(count: int) -> ClusterResult:
    """Every section in one level-0 node, for a corpus too small to cluster.

    No reduction ran, so there are no coordinates to keep: the next build inits
    fresh, which is correct — there is no layout to preserve.
    """
    return ClusterResult(
        labels=tuple(0 for _ in range(count)),
        attached=tuple(False for _ in range(count)),
        assignment_similarity=tuple(None for _ in range(count)),
        coords=(),
    )


def _load_builder() -> Builder:
    try:
        from hrono.cluster.build import build_clusters
    except ImportError as exc:
        raise ClusterError("clustering backend is not installed") from exc
    return build_clusters


OPS["cluster"] = cluster
