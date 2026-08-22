import numpy as np
import pytest

from hrono.cluster import ClusterError
from hrono.cluster.build import UMAP_DIMS, ClusterResult, build_clusters


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
    assert len(result.coords) == len(vectors)
    assert all(len(coord) == UMAP_DIMS for coord in result.coords)


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
    reduce = lambda vecs, init: np.zeros((len(vecs), UMAP_DIMS))  # noqa: E731
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
    init = [[0.5] * UMAP_DIMS, [0.6] * UMAP_DIMS]
    seen: dict[str, object] = {}

    def reduce(vecs: np.ndarray, passed_init: np.ndarray | None) -> np.ndarray:
        seen["init"] = passed_init
        return np.zeros((len(vecs), UMAP_DIMS))

    build_clusters(vectors, init=init, reduce=reduce, cluster=_labeler([0, 0]))
    assert seen["init"] is not None
    assert np.allclose(seen["init"], init)


def test_all_noise_fails_cleanly() -> None:
    vectors = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
    with pytest.raises(ClusterError, match="no clusters"):
        build_clusters(
            vectors,
            reduce=lambda vecs, init: np.zeros((len(vecs), UMAP_DIMS)),
            cluster=_labeler([-1, -1]),
        )


def test_empty_input_fails_cleanly() -> None:
    with pytest.raises(ClusterError, match="no vectors"):
        build_clusters([])


def test_result_shape_is_frozen() -> None:
    result = build_clusters(
        np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32),
        reduce=lambda vecs, init: np.zeros((len(vecs), UMAP_DIMS)),
        cluster=_labeler([0, 0]),
    )
    assert isinstance(result, ClusterResult)
    with pytest.raises(AttributeError):
        result.labels = (1,)  # type: ignore[misc]
