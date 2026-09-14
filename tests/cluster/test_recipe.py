"""#094: the clustering recipe scales with the point count."""

import pytest

from hrono.cluster import ClusterError
from hrono.cluster.recipe import LADDER, MIN_POINTS, recipe_for


def test_the_settled_leaf_recipe_serves_large_levels() -> None:
    recipe = recipe_for(5000)
    assert (recipe.n_components, recipe.min_cluster_size) == (25, 5)


def test_a_level_too_small_for_the_leaf_recipe_steps_down() -> None:
    # 26 points cannot support UMAP-25 (needs n_components + 2), so the
    # smaller spec recipe (UMAP-10, min_cluster_size 3) takes over.
    assert recipe_for(27).n_components == 25
    small = recipe_for(26)
    assert (small.n_components, small.min_cluster_size) == (10, 3)
    assert recipe_for(MIN_POINTS).n_components == 10


def test_below_the_smallest_rung_is_a_cluster_error() -> None:
    with pytest.raises(ClusterError, match="too few vectors"):
        recipe_for(MIN_POINTS - 1)
    with pytest.raises(ClusterError, match="too few vectors"):
        recipe_for(1)


def test_every_rung_is_runnable_at_its_own_floor() -> None:
    # UMAP's spectral init asks for n_components + 1 eigenvectors of an
    # N-point graph, and n_neighbors must stay under N: a rung whose floor
    # violates either is a rung that raises a driver exception in production.
    for recipe in LADDER:
        assert recipe.min_points >= recipe.n_components + 2
        assert recipe.n_neighbors < recipe.min_points
        assert recipe.min_cluster_size <= recipe.min_points


def test_the_ladder_descends() -> None:
    floors = [recipe.min_points for recipe in LADDER]
    assert floors == sorted(floors, reverse=True)
