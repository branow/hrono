"""Reusable clustering-quality harness: plant known groups, score recovery.

Clustering correctness is not what a normal unit test checks, so this harness
plants K well-separated groups (plus genuine noise points) in synthetic combined
vectors under a FIXED seed, runs the real #040 build, and scores the recovered
labels against the planted ones with the adjusted Rand index. A correct recipe
clears ``RECOVERY_THRESHOLD`` comfortably (ARI ~1.0 on the canonical fixture); a
recipe whose baked constants are perturbed (no UMAP, wrong ``min_cluster_size``)
drops well below it. Everything is offline and deterministic: synthetic
vectors, no model weights, a fixed seed.

``adjusted_rand_index`` is implemented here rather than imported so the harness
does not couple to a transitive scikit-learn install.
"""

from __future__ import annotations

from collections.abc import Callable

import hdbscan
import numpy as np

from hrono.cluster.build import ClusterResult, build_clusters

RECOVERY_THRESHOLD = 0.80


def planted_groups(
    *,
    groups: int = 5,
    per_group: int = 14,
    dim: int = 80,
    spread: float = 0.18,
    noise: int = 6,
    seed: int = 0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (combined vectors, true labels) with K planted unit-vector blobs.

    Each of ``groups`` clusters is ``per_group`` unit vectors scattered around a
    random centre by ``spread``; ``noise`` extra random unit points carry the
    label -1 (genuine noise, excluded from the recovery score but still expected
    to be attached). The defaults are the canonical fixture: the correct recipe
    recovers it at ARI ~1.0 while perturbed recipes fall far below threshold.
    """
    rng = np.random.default_rng(seed)
    vectors: list[np.ndarray] = []
    labels: list[int] = []
    for group in range(groups):
        centre = rng.normal(size=dim)
        centre /= np.linalg.norm(centre)
        points = centre + spread * rng.normal(size=(per_group, dim))
        points /= np.linalg.norm(points, axis=1, keepdims=True)
        vectors.append(points)
        labels += [group] * per_group
    for _ in range(noise):
        point = rng.normal(size=dim)
        point /= np.linalg.norm(point)
        vectors.append(point[None, :])
        labels.append(-1)
    return np.vstack(vectors).astype(np.float32), np.array(labels)


def recovery(result: ClusterResult, true_labels: np.ndarray) -> float:
    """Adjusted Rand index of recovered vs planted labels, over non-noise."""
    predicted = np.array(result.labels)
    mask = true_labels >= 0
    return adjusted_rand_index(true_labels[mask], predicted[mask])


def build_recovery(
    vectors: np.ndarray, true_labels: np.ndarray, **kwargs
) -> float:
    """Run the build and score recovery; a collapsed build recovers nothing.

    A recipe so broken it fails (``ClusterError``) is scored 0.0 — the worst
    possible recovery — so the teeth tests treat a failure and a low ARI the
    same way: below threshold. A collapse to one topic scores 0.0 by itself.
    """
    from hrono.cluster import ClusterError

    try:
        result = build_clusters(vectors, **kwargs)
    except ClusterError:
        return 0.0
    return recovery(result, true_labels)


def no_umap_reduce(vectors: np.ndarray, init: np.ndarray | None) -> np.ndarray:
    """A degenerate reducer that skips UMAP entirely (identity passthrough)."""
    return vectors


def leaf_clusterer(min_cluster_size: int) -> Callable[[np.ndarray], np.ndarray]:
    """HDBSCAN leaf clusterer with a caller-chosen (possibly wrong) min size."""

    def cluster(reduced: np.ndarray) -> np.ndarray:
        return hdbscan.HDBSCAN(
            min_cluster_size=min_cluster_size,
            metric="euclidean",
            cluster_selection_method="leaf",
        ).fit_predict(reduced)

    return cluster


def adjusted_rand_index(
    true_labels: np.ndarray, pred_labels: np.ndarray
) -> float:
    """Adjusted Rand index of two labelings (1.0 = identical partitions)."""
    true_ids = {label: i for i, label in enumerate(np.unique(true_labels))}
    pred_ids = {label: i for i, label in enumerate(np.unique(pred_labels))}
    table = np.zeros((len(true_ids), len(pred_ids)), dtype=np.int64)
    for t, p in zip(true_labels, pred_labels, strict=True):
        table[true_ids[int(t)], pred_ids[int(p)]] += 1

    def comb2(counts: np.ndarray) -> np.int64:
        return np.sum(counts * (counts - 1) // 2)

    sum_cells = comb2(table)
    sum_rows = comb2(table.sum(axis=1))
    sum_cols = comb2(table.sum(axis=0))
    n = int(table.sum())
    total = n * (n - 1) // 2
    if total == 0:
        return 1.0
    expected = sum_rows * sum_cols / total
    max_index = (sum_rows + sum_cols) / 2
    if max_index == expected:
        return 1.0
    return float((sum_cells - expected) / (max_index - expected))
