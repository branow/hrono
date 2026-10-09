"""Recall answers from the tree it was asked, and not the one beside it.

Sized like `test_engine`'s corpus and for the same reason: the vector leg
z-scores over its own distribution, so max z ~ sqrt(N-1) and under ~13 passages
it can never fire. A two-tree test therefore needs a real corpus PER TREE --
which is why a cross-tree leak cannot be shown with a fixture small enough to
read in one screen.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass

import pytest

from hrono.cluster.blend import path_body, register_path_bodies
from hrono.db.database import Database
from hrono.embed.store import upsert_vector
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from hrono.recall import fts, keyword_leg, vector_leg
from hrono.recall.engine import recall
from hrono.recall.scope import passages_of
from hrono.registry import store as registry_store

MODEL = "emb"
DIMS = 8


def unit(index: int) -> list[float]:
    vec = [0.0] * DIMS
    vec[index] = 1.0
    return vec


def const_encode(vec: list[float]):
    def encode(texts: list[str]) -> list[list[float]]:
        return [vec for _ in texts]

    return encode


def add_passage(
    conn: object,
    body: bytes,
    content_vec: list[float],
    *,
    source: str,
    path: str,
    source_type: str = "git",
) -> str:
    digest = content_hash(body)
    upsert_content(conn, digest, body)  # type: ignore[arg-type]
    upsert_vector(conn, digest, MODEL, content_vec)  # type: ignore[arg-type]
    section_id = insert_section(
        conn,  # type: ignore[arg-type]
        source=source,
        address=Address(source_type, f"ex/{source}", path, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )
    uri = f"{source_type}://ex/{source}/{path}@v1"
    conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO passages(section_id, source, source_type, instance, path, "
        "version, uri, byte_start, byte_end, content_hash, sp_paths, ordinal, "
        "created_at) VALUES (?, ?, ?, ?, ?, 'v1', ?, 0, ?, ?, '[]', 0, 't')",
        (
            section_id,
            source,
            source_type,
            f"ex/{source}",
            path,
            uri,
            len(body),
            digest,
        ),
    )
    fts.index_passage(  # production indexes every passage; so must a fixture
        conn,  # type: ignore[arg-type]
        passage_id=int(
            conn.execute("SELECT MAX(id) FROM passages").fetchone()[0]
        ),
        source=source,
        path=path,
        body=body.decode(),
    )
    return uri


def _corpus(
    conn: object,
    source: str,
    answer: bytes | None,
    *,
    size: int = 16,
    filler: int = 1,
    mention: bool = False,
) -> str | None:
    """A corpus from one source; the planted answer first if given.

    ``size`` and ``filler`` differ between the two trees on purpose: a z is a
    statement about a population, and two identically shaped corpora have the
    same median and MAD combined as apart, so a symmetric fixture cannot show
    the population changing at all.
    """
    paths = [f"{source}/f{i}.py" for i in range(size)]
    register_path_bodies(conn, paths)  # type: ignore[arg-type]
    for path in paths:
        upsert_vector(  # type: ignore[arg-type]
            conn, content_hash(path_body(path)), MODEL, unit(2)
        )
    planted: str | None = None
    for i, path in enumerate(paths):
        if i == 0 and answer is not None:
            planted = add_passage(
                conn, answer, unit(0), source=source, path=path
            )
            continue
        # some filler MENTIONS the query term without answering it: the
        # keyword z is measured over the passages that matched at all, so
        # without this each tree matches exactly one passage and the two
        # populations are the same single-item distribution.
        body = (
            f"authentication notes for {source} topic {i}\n"
            if mention and i % 3 == 0
            else f"unrelated {source} topic {i}\n"
        )
        add_passage(conn, body.encode(), unit(filler), source=source, path=path)
    return planted


ALPHA_ANSWER = b"the authentication flow issues bearer tokens\n"
BETA_ANSWER = b"the authentication flow refreshes bearer tokens\n"


@dataclass(frozen=True)
class Answers:
    alpha: str
    beta: str


@pytest.fixture
def two_trees(tmp_path: object) -> Iterator[tuple[Database, Answers]]:
    """Two corpora, each with its own answer to the same question."""
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        for name in ("alpha-src", "beta-src"):
            registry_store.insert(
                conn,  # type: ignore[arg-type]
                "sources",
                name,
                json.dumps(
                    {
                        "name": name,
                        "type": "git",
                        "url": f"https://ex/{name}.git",
                        "auth": None,
                    }
                ),
                None,
                "t",
            )
            registry_store.insert(
                conn,  # type: ignore[arg-type]
                "trees",
                name.removesuffix("-src"),
                json.dumps(
                    {"name": name.removesuffix("-src"), "sources": [name]}
                ),
                None,
                "t",
            )
        # an answer in EACH tree, alike enough that one query matches both:
        # without that, "alpha returned no beta hit" would also be true of an
        # alpha that returned nothing at all.
        mine = _corpus(conn, "alpha-src", ALPHA_ANSWER)
        theirs = _corpus(
            conn, "beta-src", BETA_ANSWER, size=28, filler=3, mention=True
        )
    assert mine is not None and theirs is not None
    yield database, Answers(alpha=mine, beta=theirs)
    database.close()


def test_a_tree_does_not_answer_from_the_tree_beside_it(
    two_trees: tuple[Database, Answers],
) -> None:
    # the defect: `POST /trees/alpha/recall` took the tree in its URL and
    # discarded it, so alpha answered with beta's corpus.
    database, answers = two_trees

    with database.connect() as conn:
        result = recall(
            conn,
            "authentication?",
            MODEL,
            const_encode(unit(0)),
            tree="alpha",
        )

    assert result.hits  # alpha HAS an answer, so a miss here is not a pass
    assert result.hits[0].uri == answers.alpha
    assert all("beta" not in hit.uri for hit in result.hits)


def test_the_tree_that_owns_the_answer_still_finds_it(
    two_trees: tuple[Database, Answers],
) -> None:
    # the other half: scoping must not cost a tree its own content, and a z
    # measured over beta's own passages is what lets this one qualify.
    database, answers = two_trees

    with database.connect() as conn:
        result = recall(
            conn, "authentication?", MODEL, const_encode(unit(0)), tree="beta"
        )

    assert result.message is None
    assert result.hits
    assert result.hits[0].uri == answers.beta
    assert all("alpha" not in hit.uri for hit in result.hits)


def test_an_undeclared_tree_searches_everything(
    two_trees: tuple[Database, Answers],
) -> None:
    # the single-corpus case: a tree with no declared sources is UNSCOPED, not
    # empty, so a database nobody has partitioned answers exactly as before.
    database, answers = two_trees

    with database.connect() as conn:
        result = recall(
            conn,
            "authentication?",
            MODEL,
            const_encode(unit(0)),
            tree="nobody-declared-me",
        )

    assert result.hits
    found = {hit.uri for hit in result.hits}
    assert found & {answers.alpha, answers.beta}


def test_a_brief_passage_belongs_to_its_node_s_tree(
    two_trees: tuple[Database, Answers],
) -> None:
    """A brief has no source of its own, so it needs the other join.

    Its ``source`` is the synthetic ``node-<id>``, which matches no
    registered source -- so a scope built only from `sections.source` would
    drop every brief from every tree, and recall would quietly stop answering
    from the summaries the whole upper tree exists to produce.
    """
    database, _answers = two_trees
    with database.connect() as conn, conn:
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES ('beta', 0, 0, 't')"
        )
        node = int(conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0])
        add_passage(
            conn,
            b"a summary of the authentication topic\n",
            unit(0),
            source=f"node-{node}",
            path=f"node-{node}",
            source_type="node",
        )

    with database.connect() as conn:
        from hrono.recall.scope import passages_of

        beta = passages_of(conn, "beta")
        alpha = passages_of(conn, "alpha")
    brief = _brief_passage_id(database)
    assert beta is not None and alpha is not None
    assert brief in beta
    assert brief not in alpha


def _brief_passage_id(database: Database) -> int:
    with database.connect() as conn:
        return int(
            conn.execute(
                "SELECT id FROM passages WHERE source_type = 'node'"
            ).fetchone()["id"]
        )


def test_each_leg_scores_over_its_own_tree_s_population(
    two_trees: tuple[Database, Answers],
) -> None:
    """The PO ruling of 2026-09-25, as a test on each leg separately.

    The fused result cannot show this: both legs must agree before a passage
    becomes a hit, so ONE leg filtering is enough to keep another tree's
    passage out of the answer. What one leg cannot do alone is keep the other
    tree out of the DISTRIBUTION -- and a z is a statement about a population.
    Drop either filter and every score silently changes while the hit set
    stays right, which is why this is asserted per leg.
    """
    database, _answers = two_trees
    with database.connect() as conn:
        scope = passages_of(conn, "alpha")
        assert scope is not None

        scoped_vec = vector_leg.scores(conn, unit(0), MODEL, scope)
        whole_vec = vector_leg.scores(conn, unit(0), MODEL, None)
        scoped_kw = keyword_leg.scores(conn, "authentication", scope)
        whole_kw = keyword_leg.scores(conn, "authentication", None)

    assert set(scoped_vec) <= scope
    assert set(scoped_kw) <= scope
    assert set(whole_vec) - scope  # the unscoped run really does see beta
    assert set(whole_kw) - scope

    # and the population changes the number, not only the membership
    shared = set(scoped_vec) & set(whole_vec)
    assert any(scoped_vec[pid] != whole_vec[pid] for pid in shared)
    shared_kw = set(scoped_kw) & set(whole_kw)
    assert any(scoped_kw[pid] != whole_kw[pid] for pid in shared_kw)


def test_an_unscoped_tree_still_answers_only_from_its_own_briefs(
    two_trees: tuple[Database, Answers],
) -> None:
    # "unscoped" widens a tree's CONTENT to every source; it must not hand it
    # every other tree's summaries too. A brief is tree-owned data wherever it
    # lives.
    database, _answers = two_trees
    with database.connect() as conn, conn:
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES ('beta', 0, 0, 't')"
        )
        node = int(conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0])
        add_passage(
            conn,
            b"a summary of the authentication topic\n",
            unit(0),
            source=f"node-{node}",
            path=f"node-{node}",
            source_type="node",
        )

    with database.connect() as conn:
        from hrono.recall.scope import passages_of

        undeclared = passages_of(conn, "nobody-declared-me")
        content = {
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM passages WHERE source_type != 'node'"
            ).fetchall()
        }
    brief = _brief_passage_id(database)
    assert brief not in undeclared  # beta's summary is beta's alone
    assert content <= undeclared  # every content passage is still searched
