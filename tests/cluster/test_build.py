import numpy as np
import pytest

from hrono.cluster import ClusterError
from hrono.cluster.build import ClusterResult, build_clusters, core_labels
from hrono.cluster.recipe import MIN_POINTS, recipe_for

STUB_DIMS = 4  # any width: the stub reducers below stand in for UMAP


def planted_vectors(
    groups: int = 5, per_group: int = 12, dim: int = 64, spread: float = 0.05
) -> tuple[np.ndarray, np.ndarray]:
    """Well-separated unit vectors with a known group label per point."""
    rng = np.random.default_rng(0)
    points, labels = [], []
    for group in range(groups):
        center = rng.normal(size=dim)
        center /= np.linalg.norm(center)
        pts = center + spread * rng.normal(size=(per_group, dim))
        pts /= np.linalg.norm(pts, axis=1, keepdims=True)
        points.append(pts)
        labels += [group] * per_group
    return np.vstack(points).astype(np.float32), np.array(labels)


def test_recovers_planted_groups_with_full_coverage() -> None:
    vectors, truth = planted_vectors()
    result = build_clusters(vectors)

    labels = np.array(result.labels)
    assert (labels >= 0).all()  # every point assigned, no residual noise
    # each planted group collapses to exactly one recovered label
    for group in range(5):
        assert len(set(labels[truth == group].tolist())) == 1
    # and distinct planted groups map to distinct labels
    recovered = {int(labels[truth == group][0]) for group in range(5)}
    assert len(recovered) == 5


def test_is_deterministic_under_the_fixed_seed() -> None:
    vectors, _ = planted_vectors()
    first = build_clusters(vectors)
    second = build_clusters(vectors)
    assert first.labels == second.labels
    assert np.allclose(first.coords, second.coords)


def test_coords_have_the_reduced_dimensionality() -> None:
    vectors, _ = planted_vectors()
    result = build_clusters(vectors)
    dims = recipe_for(len(vectors)).n_components
    assert len(result.coords) == len(vectors)
    assert all(len(coord) == dims for coord in result.coords)


def _labeler(labels: list[int]):
    return lambda reduced: np.array(labels)


def test_noise_attaches_to_nearest_cluster_in_combined_space() -> None:
    # two tight clusters plus two noise points, one leaning to each cluster.
    vectors = np.array(
        [
            [1.0, 0.0],
            [1.0, 0.0],
            [0.0, 1.0],
            [0.0, 1.0],
            [0.9, 0.1],  # noise near cluster 0
            [0.1, 0.9],  # noise near cluster 1
        ],
        dtype=np.float32,
    )
    reduce = lambda vecs, init: np.zeros((len(vecs), STUB_DIMS))  # noqa: E731
    result = build_clusters(
        vectors, reduce=reduce, cluster=_labeler([0, 0, 1, 1, -1, -1])
    )

    assert result.labels == (0, 0, 1, 1, 0, 1)  # noise joined nearest cluster
    assert result.attached == (False, False, False, False, True, True)
    core = result.assignment_similarity[:4]
    assert all(value is None for value in core)  # cores carry no similarity
    assert result.assignment_similarity[4] is not None
    assert result.assignment_similarity[5] is not None


def test_warm_init_coords_reach_the_reducer() -> None:
    vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    init = [[0.5] * STUB_DIMS, [0.6] * STUB_DIMS]
    seen: dict[str, object] = {}

    def reduce(vecs: np.ndarray, passed_init: np.ndarray | None) -> np.ndarray:
        seen["init"] = passed_init
        return np.zeros((len(vecs), STUB_DIMS))

    build_clusters(vectors, init=init, reduce=reduce, cluster=_labeler([0, 0]))
    assert seen["init"] is not None
    assert np.allclose(seen["init"], init)


def test_all_noise_is_one_topic_of_density_members() -> None:
    vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    result = build_clusters(
        vectors,
        reduce=lambda vecs, init: np.ones((len(vecs), STUB_DIMS)),
        cluster=_labeler([-1, -1]),
    )
    assert result.labels == (0, 0)
    assert result.attached == (False, False)
    assert result.assignment_similarity == (None, None)
    assert result.coords == ((1.0,) * STUB_DIMS,) * 2
    assert result.collapsed is True


def test_a_build_with_a_core_is_not_collapsed() -> None:
    vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    result = build_clusters(
        vectors,
        reduce=lambda vecs, init: np.ones((len(vecs), STUB_DIMS)),
        cluster=_labeler([0, -1]),
    )
    assert result.collapsed is False


def structureless(count: int, dim: int = 384, seed: int = 0) -> np.ndarray:
    """Unit vectors with no density anywhere: real HDBSCAN finds no cluster."""
    points = np.random.default_rng(seed).normal(size=(count, dim))
    return points / np.linalg.norm(points, axis=1, keepdims=True)


def test_real_recipe_makes_a_structureless_level_one_topic() -> None:
    # the real reducer and clusterer label every point of this
    # level noise (core_labels proves it), and the build answers one topic
    # rather than failing the run.
    vectors = structureless(30)
    assert set(core_labels(vectors)) == {-1}
    result = build_clusters(vectors)
    assert result.labels == (0,) * 30
    assert len(result.coords) == 30
    assert result.collapsed is True


def test_empty_input_fails_cleanly() -> None:
    with pytest.raises(ClusterError, match="no vectors"):
        build_clusters([])


def test_result_shape_is_frozen() -> None:
    result = build_clusters(
        np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        reduce=lambda vecs, init: np.zeros((len(vecs), STUB_DIMS)),
        cluster=_labeler([0, 0]),
    )
    assert isinstance(result, ClusterResult)
    with pytest.raises(AttributeError):
        result.labels = (1,)  # type: ignore[misc]


@pytest.mark.parametrize("count", [1, 4, 10, MIN_POINTS - 1])
def test_real_recipe_refuses_a_level_it_cannot_reduce(count: int) -> None:
    # below the smallest rung of the clustering ladder there is no honest
    # reduction — the caller must see ClusterError ("this level cannot be
    # reduced further"), never a scipy/numba driver exception.
    vectors, _ = planted_vectors(groups=1, per_group=count)
    with pytest.raises(ClusterError, match="too few vectors"):
        build_clusters(vectors)
    with pytest.raises(ClusterError, match="too few vectors"):
        core_labels(vectors)


@pytest.mark.parametrize("count", [MIN_POINTS, 26, 27, 40])
def test_real_recipe_clusters_every_size_it_accepts(count: int) -> None:
    # the sizes around the old UMAP-25 breaking point (26/27) run the REAL
    # reducer and clusterer end to end: scaled parameters, full coverage.
    vectors, _ = planted_vectors(groups=2, per_group=count // 2 + 1)
    vectors = vectors[:count]
    result = build_clusters(vectors)
    dims = recipe_for(count).n_components
    assert len(result.labels) == count
    assert all(label >= 0 for label in result.labels)
    assert all(len(coord) == dims for coord in result.coords)
    assert len(core_labels(vectors)) == count


@pytest.mark.parametrize(("stale_width", "count"), [(25, 20), (10, 40)])
def test_real_recipe_drops_a_warm_init_from_another_rung(
    stale_width: int, count: int
) -> None:
    # stored coords carry the width of the build that wrote them, so a
    # level that has crossed a rung since offers an init this recipe cannot
    # reduce to. The build must run cold rather than fail — identical to one
    # given no init at all — in both directions across the boundary.
    dims = recipe_for(count).n_components
    assert stale_width != dims
    vectors, _ = planted_vectors(groups=2, per_group=count // 2)
    stale = np.random.default_rng(1).normal(size=(count, stale_width))

    warm = build_clusters(vectors, init=stale)
    cold = build_clusters(vectors)

    assert all(len(coord) == dims for coord in warm.coords)
    assert np.allclose(warm.coords, cold.coords)


def test_real_recipe_honours_a_warm_init_of_its_own_width() -> None:
    # the width guard drops only a mismatched init: a usable one still steers
    # the layout, which is what warm reconciliation depends on.
    vectors, _ = planted_vectors(groups=2, per_group=20)
    dims = recipe_for(len(vectors)).n_components
    init = np.random.default_rng(1).normal(size=(len(vectors), dims))

    warm = build_clusters(vectors, init=init)
    cold = build_clusters(vectors)

    assert not np.allclose(warm.coords, cold.coords)
