"""Weighted RRF fusion of the two recall legs."""

from hrono.recall.fusion import (
    CAP,
    EXPLORE_MESSAGE,
    fuse,
)


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


def test_a_dominant_document_is_held_to_its_share_while_others_qualify() -> (
    None
):
    # one document may fill all ten slots, but only once nobody else wants
    # one.
    hits = [(i, 1.0 - i / 100) for i in range(1, 13)]
    documents = {i: ("hog" if i <= 9 else f"other-{i}") for i in range(1, 13)}

    fused = fuse(hits, [], documents)

    ids = fused.hits
    assert len(ids) == CAP
    # every other document got a slot: none was starved by the leader
    assert {documents[i] for i in ids} == {
        "hog",
        "other-10",
        "other-11",
        "other-12",
    }
    # and the leader was held to its share UNTIL they had theirs — its fifth
    # hit lands after every other document is placed, never before
    hog = [n for n, i in enumerate(ids) if documents[i] == "hog"]
    others = [n for n, i in enumerate(ids) if documents[i] != "hog"]
    assert hog[:4] == [0, 1, 2, 3]
    assert max(others) < hog[4]
    # it exceeds four only on slots nobody else wanted: a hard cap would have
    # returned seven hits here, the reserve returns a full window
    assert len(hog) == CAP - len(others)


def test_the_leader_keeps_the_window_when_nothing_else_qualifies() -> None:
    # "generate a version 7 uuid" answers from ONE file. Truncating it to four
    # hits to make room for nothing would serve a metric, not a reader.
    hits = [(i, 1.0 - i / 100) for i in range(1, 13)]
    documents = dict.fromkeys(range(1, 13), "the-only-answer")

    fused = fuse(hits, [], documents)

    assert len(fused.hits) == CAP
    assert fused.hits == tuple(range(1, 11))  # best ten, in score order


def test_a_window_that_cannot_be_filled_comes_back_short() -> None:
    # never padded with anything that did not qualify: the union IS the
    # candidate set, so a short union is a short window.
    hits = [(1, 0.9), (2, 0.8)]
    documents = {1: "a", 2: "a"}

    fused = fuse(hits, [], documents)

    assert fused.hits == (1, 2)
    assert fused.message is None


def test_the_reserve_preserves_score_order_within_the_window() -> None:
    # the reserve decides WHICH passages, never their order relative to each
    # other: a deferred hit that comes back still sits where its score puts it.
    hits = [(i, 1.0 - i / 100) for i in range(1, 8)]
    documents = {i: ("hog" if i <= 6 else "other") for i in range(1, 8)}

    ids = fuse(hits, [], documents).hits

    assert ids[:4] == (1, 2, 3, 4)  # the hog's share, best first
    assert 7 in ids  # the other document got its turn
    assert ids.index(7) == 4  # ... immediately after the share
    assert ids[5:] == (5, 6)  # then the deferred remainder, in order


def test_without_documents_the_window_is_pure_score_order() -> None:
    hits = [(i, 1.0 - i / 100) for i in range(1, 13)]

    assert fuse(hits, []).hits == tuple(range(1, 11))


def test_one_empty_leg_is_ranked_by_the_other_alone() -> None:
    # the keyword leg qualified no passage on a ~120-section test corpus, so
    # this is not an edge case — it is every query we have measured. The fusion
    # must rank cleanly from one leg, and the weighting must not scale the
    # surviving scores into meaninglessness.
    vector_only = fuse([(1, 9.0), (2, 8.0), (3, 7.0)], [])
    keyword_only = fuse([], [(1, 9.0), (2, 8.0), (3, 7.0)])

    assert vector_only.hits == (1, 2, 3)
    assert keyword_only.hits == (1, 2, 3)
    assert vector_only.message is None
    # each leg alone contributes only its own weight, and order is preserved
    assert vector_only.ranked[0][1] > vector_only.ranked[1][1]
    assert keyword_only.ranked[0][1] > keyword_only.ranked[1][1]
