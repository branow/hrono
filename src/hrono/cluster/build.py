"""The full cluster build: UMAP reduce -> HDBSCAN leaf -> noise attach.

Given the sections' combined vectors (#039), the settled recipe (clustering-
lifecycle.md, how-hrono-works.md) is:

1. **UMAP** to the recipe's dims, ``metric="cosine"``, a fixed seed — the
   nonlinear reduction creates the density contrast HDBSCAN needs. A warm-init
   seam (``init`` = stored coords) is wired for later incremental settle (#T39);
   a fresh full build inits from UMAP's default. Stored coords carry the width
   of the build that wrote them, so a level that has crossed a rung since then
   offers an init of the wrong width; that init is dropped and the build runs
   cold rather than failing, and its own coords — written at the new width by
   ``store.replace_tree`` — warm the next build.
2. **HDBSCAN** on the reduced vectors, the recipe's ``min_cluster_size``,
   ``metric="euclidean"``, ``cluster_selection_method="leaf"`` — leaf selection
   yields the many small clusters a summarisation tree wants.
3. **Attach** every HDBSCAN noise point (-1) to its nearest cluster in the
   ORIGINAL combined space (nearest density-core member by dot product, which
   for unit-blended vectors is cosine), so every section lands in exactly one
   topic. Attached members carry the attachment similarity; density-core members
   do not.

The parameters that scale with the point count (dims, neighbours, minimum
cluster size) come from ``recipe`` — the same machinery reduces a level of
thousands of sections and a level of tens of briefs, with the recipe scaled to
what it is given (how-hrono-works.md); the rest is baked here, not config. The
heavy numeric libraries are imported lazily so a missing ``cluster`` extra
surfaces as a clean ``ClusterError`` rather than an import traceback, mirroring
the embed backend — and a driver failure inside them is translated to
``ClusterError`` too, so no scipy/numba traceback escapes the backend.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

import numpy as np

from hrono.cluster import ClusterError
from hrono.cluster.recipe import recipe_for

UMAP_METRIC = "cosine"
UMAP_SEED = 42
HDBSCAN_METRIC = "euclidean"
SELECTION_METHOD = "leaf"

Reducer = Callable[[np.ndarray, np.ndarray | None], np.ndarray]
Clusterer = Callable[[np.ndarray], np.ndarray]


@dataclass(frozen=True)
class ClusterResult:
    """One entry per input vector, aligned to the input order.

    ``labels`` is the final topic label (>= 0 for every vector — noise is
    attached). ``attached`` is True for a section that was HDBSCAN noise and was
    attached by proximity; ``assignment_similarity`` is its combined-space
    similarity to the cluster it joined (None for density-core members).
    ``coords`` is the reduced position, kept for warm-init and the graph.
    """

    labels: tuple[int, ...]
    attached: tuple[bool, ...]
    assignment_similarity: tuple[float | None, ...]
    coords: tuple[tuple[float, ...], ...]


def build_clusters(
    combined: Sequence[Sequence[float]],
    *,
    init: Sequence[Sequence[float]] | None = None,
    reduce: Reducer | None = None,
    cluster: Clusterer | None = None,
) -> ClusterResult:
    """Reduce, cluster, and attach noise; return per-section membership."""
    vectors = np.asarray(combined, dtype=np.float32)
    if vectors.ndim != 2 or len(vectors) == 0:
        raise ClusterError("no vectors to cluster")
    reducer = reduce if reduce is not None else _default_reduce
    clusterer = cluster if cluster is not None else _default_cluster
    init_coords = None if init is None else np.asarray(init, dtype=np.float32)

    reduced = np.asarray(reducer(vectors, init_coords), dtype=np.float32)
    labels = np.asarray(clusterer(reduced))
    labels, attached, sims = _attach_noise(vectors, labels)

    return ClusterResult(
        labels=tuple(int(value) for value in labels),
        attached=tuple(bool(value) for value in attached),
        assignment_similarity=tuple(
            None if np.isnan(value) else float(value) for value in sims
        ),
        coords=tuple(tuple(float(v) for v in row) for row in reduced),
    )


def _attach_noise(
    vectors: np.ndarray, labels: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Attach each noise point to its nearest cluster in combined space."""
    labels = labels.copy()
    attached = labels == -1
    sims = np.full(len(labels), np.nan)
    noise_idx = np.where(labels == -1)[0]
    core_idx = np.where(labels >= 0)[0]
    if len(core_idx) == 0:
        raise ClusterError("clustering produced no clusters")
    if len(noise_idx):
        scores = vectors[noise_idx] @ vectors[core_idx].T
        nearest = scores.argmax(axis=1)
        labels[noise_idx] = labels[core_idx[nearest]]
        sims[noise_idx] = scores[np.arange(len(noise_idx)), nearest]
    return labels, attached, sims


def core_labels(combined: Sequence[Sequence[float]]) -> tuple[int, ...]:
    """Scoped mini-pipeline for the incubator (#086): UMAP -> HDBSCAN leaf,
    returning the raw density labels WITHOUT attaching noise (-1 stays -1).

    Unlike ``build_clusters`` (which attaches every noise point to a core), the
    drain emits only density-core clusters and leaves residual noise to be
    force-assigned to an existing cluster — so it needs the un-attached labels.
    """
    vectors = np.asarray(combined, dtype=np.float32)
    if vectors.ndim != 2 or len(vectors) == 0:
        raise ClusterError("no vectors to cluster")
    reduced = _default_reduce(vectors, None)
    return tuple(int(label) for label in _default_cluster(reduced))


def _default_reduce(vectors: np.ndarray, init: np.ndarray | None) -> np.ndarray:
    recipe = recipe_for(len(vectors))
    umap = _umap()
    kwargs: dict[str, object] = {
        "n_components": recipe.n_components,
        "n_neighbors": recipe.n_neighbors,
        "metric": UMAP_METRIC,
        "random_state": UMAP_SEED,
    }
    if _fits(init, recipe.n_components):
        kwargs["init"] = init
    try:
        return umap.UMAP(**kwargs).fit_transform(vectors)
    except Exception as exc:
        raise ClusterError("the reduction failed on these vectors") from exc


def _fits(init: np.ndarray | None, n_components: int) -> bool:
    """True when a warm init has the width this build's recipe reduces to."""
    return init is not None and init.ndim == 2 and init.shape[1] == n_components


def _default_cluster(reduced: np.ndarray) -> np.ndarray:
    recipe = recipe_for(len(reduced))
    hdbscan = _hdbscan()
    try:
        return hdbscan.HDBSCAN(
            min_cluster_size=recipe.min_cluster_size,
            metric=HDBSCAN_METRIC,
            cluster_selection_method=SELECTION_METHOD,
        ).fit_predict(reduced)
    except Exception as exc:
        raise ClusterError("the clusterer failed on these vectors") from exc


def _umap() -> object:
    try:
        import umap
    except ImportError as exc:
        raise ClusterError("clustering backend is not installed") from exc
    return umap


def _hdbscan() -> object:
    try:
        import hdbscan
    except ImportError as exc:
        raise ClusterError("clustering backend is not installed") from exc
    return hdbscan
