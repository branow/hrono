"""The numpy scoring is the arithmetic the recipe describes.

The reference here is a plain, obvious loop written in the test — the
specification, not a second production path. If the two ever disagree, the
question is which one is wrong, and that is exactly the question worth being
able to ask about a frozen recipe that was calibrated by measurement.
"""

from __future__ import annotations

import math
import random
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from hrono.cluster.blend import (
    ALPHA,
    combine,
    combined_vector,
    path_body,
    register_path_bodies,
    unit,
)
from hrono.db.database import open_database
from hrono.embed.store import get_vector, upsert_vector
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.recall import vector_leg

MODEL = "emb"
DIMS = 16


def _vector(rng: random.Random) -> list[float]:
    raw = [rng.gauss(0, 1) for _ in range(DIMS)]
    norm = math.sqrt(sum(value * value for value in raw))
    return [value / norm for value in raw]


def _reference(
    conn: object, query_vec: Sequence[float], scope: frozenset[int] | None
) -> dict[int, float]:
    """A plain loop, kept here as the statement of the arithmetic."""
    query = combine(query_vec, query_vec)
    content_query = unit(query_vec)
    blended: list[tuple[int, float]] = []
    content: list[tuple[int, float]] = []
    for row in conn.execute(  # type: ignore[attr-defined]
        "SELECT id, content_hash, path FROM passages ORDER BY id"
    ).fetchall():
        if scope is not None and int(row["id"]) not in scope:
            continue
        passage = combined_vector(conn, row["content_hash"], row["path"], MODEL)  # type: ignore[arg-type]
        body = get_vector(conn, row["content_hash"], MODEL)  # type: ignore[arg-type]
        if passage is None or body is None:
            continue
        pid = int(row["id"])
        blended.append((pid, _dot(query, passage)))
        content.append((pid, _dot(content_query, unit(body))))
    if not blended:
        return {}
    by_blend = vector_leg._z_scores(blended)
    by_content = vector_leg._z_scores(content)
    return {pid: max(z, by_content.get(pid, z)) for pid, z in by_blend.items()}


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


class Corpus:
    def __init__(self, conn: object) -> None:
        self.conn = conn
        self.ids: list[int] = []

    def add(
        self,
        path: str,
        vector: Sequence[float] | None,
        path_vector: Sequence[float] | None = None,
    ) -> int:
        body = f"{path} body\n".encode()
        digest = content_hash(body)
        istore.upsert_content(self.conn, digest, body)  # type: ignore[arg-type]
        register_path_bodies(self.conn, [path])  # type: ignore[arg-type]
        if vector is not None:
            upsert_vector(self.conn, digest, MODEL, vector)  # type: ignore[arg-type]
        if path_vector is not None:
            upsert_vector(  # type: ignore[arg-type]
                self.conn, content_hash(path_body(path)), MODEL, path_vector
            )
        section = istore.insert_section(
            self.conn,  # type: ignore[arg-type]
            source="docs",
            address=Address("git", "ex/docs", path, "v1"),
            start=0,
            end=len(body),
            content_hash=digest,
            ordinal=0,
        )
        self.conn.execute(  # type: ignore[attr-defined]
            "INSERT INTO passages(section_id, source, source_type, instance, "
            "path, version, uri, byte_start, byte_end, content_hash, "
            "sp_paths, ordinal, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                section,
                "docs",
                "git",
                "ex/docs",
                path,
                "v1",
                f"git://ex/docs/{path}@v1",
                0,
                len(body),
                digest,
                "[]",
                0,
                "t",
            ),
        )
        passage_id = int(
            self.conn.execute(  # type: ignore[attr-defined]
                "SELECT MAX(id) FROM passages"
            ).fetchone()[0]
        )
        self.ids.append(passage_id)
        return passage_id


@pytest.fixture
def corpus(tmp_path: Path) -> Iterator[Corpus]:
    conn = open_database(tmp_path / "hrono.db")
    rng = random.Random(11)
    built = Corpus(conn)
    with conn:
        for i in range(40):
            built.add(f"pkg/mod{i // 7}/file{i}.md", _vector(rng), _vector(rng))
    yield built
    conn.close()


def test_the_z_scores_match_the_reference_loop(corpus: Corpus) -> None:
    rng = random.Random(3)
    query = _vector(rng)

    fast = vector_leg.scores(corpus.conn, query, MODEL)  # type: ignore[arg-type]
    slow = _reference(corpus.conn, query, None)

    assert set(fast) == set(slow)
    for passage_id, z in slow.items():
        assert fast[passage_id] == pytest.approx(z, abs=1e-9)


def test_the_ordering_is_the_same(corpus: Corpus) -> None:
    """Ranking is what a recall returns, so agreeing on ORDER is the claim."""
    rng = random.Random(4)
    query = _vector(rng)

    fast = vector_leg.scores(corpus.conn, query, MODEL)  # type: ignore[arg-type]
    slow = _reference(corpus.conn, query, None)

    assert sorted(fast, key=lambda p: -fast[p]) == sorted(
        slow, key=lambda p: -slow[p]
    )


def test_a_scoped_recall_scores_only_its_trees_passages(
    corpus: Corpus,
) -> None:
    """And the z is measured against THAT population, not the corpus."""
    rng = random.Random(5)
    query = _vector(rng)
    scope = frozenset(corpus.ids[:10])

    fast = vector_leg.scores(corpus.conn, query, MODEL, scope)  # type: ignore[arg-type]
    slow = _reference(corpus.conn, query, scope)

    assert set(fast) == scope
    for passage_id, z in slow.items():
        assert fast[passage_id] == pytest.approx(z, abs=1e-9)
    assert fast != vector_leg.scores(corpus.conn, query, MODEL)  # type: ignore[arg-type]


def test_a_passage_missing_either_vector_is_skipped(
    corpus: Corpus, tmp_path: Path
) -> None:
    """Half a blend is not a smaller score, it is a different question."""
    rng = random.Random(6)
    with corpus.conn:  # type: ignore[union-attr]
        no_body = corpus.add("pkg/nobody.md", None, _vector(rng))
        no_path = corpus.add("pkg/nopath.md", _vector(rng), None)

    scored = vector_leg.scores(corpus.conn, _vector(rng), MODEL)  # type: ignore[arg-type]

    assert no_body not in scored
    assert no_path not in scored


def test_an_empty_scope_scores_nothing(corpus: Corpus) -> None:
    assert (
        vector_leg.scores(
            corpus.conn, _vector(random.Random(7)), MODEL, frozenset()
        )  # type: ignore[arg-type]
        == {}
    )


def test_the_weights_are_content_then_path_at_an_asymmetric_alpha() -> None:
    """Pinned at alpha 0.25, because at the baked 0.5 they are equal.

    Swapping them is invisible while `ALPHA` is 0.5 — the classic property
    held by something else — so the order is asserted where the two differ.
    """
    from hrono.cluster.blend import blend_weights

    assert blend_weights(0.25) == (math.sqrt(0.75), math.sqrt(0.25))
    assert blend_weights()[0] == pytest.approx(math.sqrt(1 - ALPHA))


def test_a_dot_product_weights_each_view_by_alpha_not_its_root() -> None:
    """Both sides of the dot carry `sqrt(w)`, so each view arrives at `w`.

    Also invisible at alpha 0.5, and for a second reason: a z-score is
    invariant under scaling every score alike, so squaring or not squaring
    gives identical rankings while the two weights are equal.
    """
    from hrono.cluster.blend import similarity_weights

    assert similarity_weights(0.25) == pytest.approx((0.75, 0.25))

    body = unit([1.0, 0.0])
    path = unit([0.0, 1.0])
    query = unit([0.6, 0.8])
    content_w, path_w = similarity_weights(0.25)

    assert _dot(combine(query, query, 0.25), combine(body, path, 0.25)) == (
        pytest.approx(
            content_w * _dot(query, body) + path_w * _dot(query, path)
        )
    )
