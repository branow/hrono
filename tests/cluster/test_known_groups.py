import numpy as np

from hrono.cluster.build import build_clusters
from hrono.cluster.recipe import recipe_for
from tests.cluster.harness import (
    RECOVERY_THRESHOLD,
    adjusted_rand_index,
    build_recovery,
    leaf_clusterer,
    no_umap_reduce,
    planted_groups,
    recovery,
)


def test_planted_groups_are_recovered_above_threshold() -> None:
    vectors, truth = planted_groups()
    result = build_clusters(vectors)
    score = recovery(result, truth)
    # the correct recipe recovers the canonical fixture at ARI ~1.0, far above
    # the documented 0.80 bar.
    assert score >= RECOVERY_THRESHOLD
    assert score > 0.95


def test_every_point_is_assigned_to_exactly_one_topic() -> None:
    vectors, _ = planted_groups()
    result = build_clusters(vectors)
    labels = np.array(result.labels)
    assert len(labels) == len(vectors)
    assert (labels >= 0).all()  # no orphan/unassigned points; noise attached
    # attachment bookkeeping is consistent: a similarity iff the point was an
    # HDBSCAN-noise attachment, none for density-core members.
    for attached, sim in zip(
        result.attached, result.assignment_similarity, strict=True
    ):
        assert (sim is not None) == attached


def test_clustering_is_deterministic_under_the_fixed_seed() -> None:
    vectors, _ = planted_groups()
    first = build_clusters(vectors)
    second = build_clusters(vectors)
    assert first.labels == second.labels
    assert np.allclose(first.coords, second.coords)


def test_teeth_recovery_collapses_without_umap() -> None:
    # Dropping the UMAP reduction (identity passthrough) wrecks the density
    # contrast HDBSCAN needs: recovery falls well below threshold on the same
    # fixture the correct recipe recovers perfectly.
    vectors, truth = planted_groups()
    correct = build_recovery(vectors, truth)
    broken = build_recovery(
        vectors,
        truth,
        reduce=no_umap_reduce,
        cluster=leaf_clusterer(5),
    )
    assert correct >= RECOVERY_THRESHOLD
    assert broken < RECOVERY_THRESHOLD


def test_teeth_recovery_collapses_with_wrong_min_cluster_size() -> None:
    # A min_cluster_size larger than any planted group leaves every point as
    # noise -> no clusters -> recovery 0.0, far below threshold.
    vectors, truth = planted_groups()
    broken = build_recovery(vectors, truth, cluster=leaf_clusterer(60))
    assert broken < RECOVERY_THRESHOLD


def test_adjusted_rand_index_endpoints() -> None:
    labels = np.array([0, 0, 1, 1, 2, 2])
    assert adjusted_rand_index(labels, labels) == 1.0
    # a relabeling of the same partition is still a perfect match
    assert adjusted_rand_index(labels, np.array([2, 2, 0, 0, 1, 1])) == 1.0
    # everything lumped into one cluster carries no information -> ~0
    assert adjusted_rand_index(labels, np.zeros(6, dtype=int)) == 0.0


def test_reduced_coords_have_the_recipe_dimensionality() -> None:
    vectors, _ = planted_groups()
    result = build_clusters(vectors)
    dims = recipe_for(len(vectors)).n_components
    assert all(len(coord) == dims for coord in result.coords)
