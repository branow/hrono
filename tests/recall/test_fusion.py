"""T27: weighted RRF fusion of the two recall legs."""

from hrono.recall.fusion import (
    CAP,
    EXPLORE_MESSAGE,
    KEYWORD_WEIGHT,
    VECTOR_WEIGHT,
    K,
    fuse,
)


def test_constants_are_baked() -> None:
    assert (K, VECTOR_WEIGHT, KEYWORD_WEIGHT, CAP) == (60, 0.7, 0.3, 10)


def test_a_both_leg_passage_outranks_an_equal_single_leg_one() -> None:
    # passage 2 qualifies in both legs at rank 1; passages 1 and 3 in one each.
    vector = [(2, 9.0), (1, 8.0)]
    keyword = [(2, 9.0), (3, 8.0)]
    result = fuse(vector, keyword)
    assert result.hits[0] == 2  # composed weight puts the dual-leg hit first
    assert set(result.hits) == {1, 2, 3}
    assert result.message is None


def test_ordering_is_deterministic_on_ties() -> None:
    # 1 and 2 are both vector-only at the same rank position -> tie by id.
    a = fuse([(2, 5.0), (1, 5.0)], [])
    b = fuse([(1, 5.0), (2, 5.0)], [])
    # rank follows input order, but equal scores tie-break by id ascending
    assert a.hits == (2, 1)  # input order: 2 first (rank1) beats 1 (rank2)
    assert b.hits == (1, 2)


def test_cap_is_ten() -> None:
    vector = [(i, float(100 - i)) for i in range(15)]
    result = fuse(vector, [])
    assert len(result.hits) == 10
    assert result.hits == tuple(range(10))  # best-ranked ten, in order


def test_empty_union_returns_the_explore_message() -> None:
    result = fuse([], [])
    assert result.hits == ()
    assert result.message == "no confident matches - explore the map."
    assert result.message == EXPLORE_MESSAGE


def test_weights_compose_by_rank() -> None:
    # a vector rank-1 (0.7/61) beats a keyword rank-1 (0.3/61) alone.
    result = fuse([(1, 5.0)], [(2, 5.0)])
    assert result.hits == (1, 2)
