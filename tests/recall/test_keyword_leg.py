"""The keyword leg qualifies only at BM25 z>=6.0 WITH vector support>=3.0."""

from collections.abc import Iterator

import pytest

from hrono.db.database import Database
from hrono.recall import fts
from hrono.recall.keyword_leg import (
    VECTOR_SUPPORT,
    Z_FLOOR,
    _match_expr,
    _qualify,
    search,
)


def make_hits(
    strong: list[int], weak: int = 100
) -> tuple[tuple[int, float], ...]:
    """A BM25 result set: `strong` ids match hugely, plus `weak` weak ones."""
    hits = [(pid, -10000.0) for pid in strong]
    hits += [(1000 + i, -1.0) for i in range(weak)]
    return tuple(hits)


def test_constants_are_baked() -> None:
    assert Z_FLOOR == 6.0
    assert VECTOR_SUPPORT == 3.0


def test_strong_keyword_with_vector_support_qualifies() -> None:
    hits = make_hits([1])
    out = _qualify(hits, vector_z={1: 5.0})
    assert [pid for pid, _ in out] == [1]
    assert all(z >= Z_FLOOR for _, z in out)


def test_strong_keyword_without_vector_support_is_rejected() -> None:
    # the load-bearing case: high BM25, no semantic support -> never qualifies.
    hits = make_hits([1])
    assert _qualify(hits, vector_z={1: 2.9}) == ()  # just below support
    assert _qualify(hits, vector_z={}) == ()  # no vector hit at all


def test_only_the_vector_supported_of_two_strong_matches_qualifies() -> None:
    hits = make_hits([1, 2])
    out = _qualify(hits, vector_z={1: 4.0, 2: 0.0})
    assert [pid for pid, _ in out] == [1]  # 2 is a stopword-y match, dropped


def test_no_hits_yields_nothing() -> None:
    assert _qualify((), vector_z={1: 9.0}) == ()


def test_match_expr_ors_bare_terms_and_ignores_punctuation() -> None:
    assert _match_expr("Auth login") == '"auth" OR "login"'
    assert _match_expr("   !!!  ") is None
    assert _match_expr("") is None


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        fts.index_passage(
            conn,
            passage_id=1,
            source="repo",
            path="a.py",
            body="auth login flow",
        )
        fts.index_passage(
            conn,
            passage_id=2,
            source="repo",
            path="b.py",
            body="unrelated text",
        )
    yield database
    database.close()


def test_search_sanitizes_a_messy_query_without_crashing(db: Database) -> None:
    # a raw question full of FTS5 operators / quotes must not raise; it is
    # tokenised into bare OR-ed terms.
    with db.connect() as conn:
        result = search(conn, 'what about "auth" AND NEAR() login?', {1: 9.0})
    assert isinstance(result, tuple)  # ran cleanly (crash would raise)


def test_search_returns_empty_for_an_all_punctuation_query(
    db: Database,
) -> None:
    with db.connect() as conn:
        assert search(conn, "?!...", {1: 9.0}) == ()
