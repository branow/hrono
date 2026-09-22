"""T28 calibration: a planted answer is recovered; a strict miss -> explore.

Sizing matters (#072 review): the vector leg z-scores over the query's own
distribution, so max z ~ sqrt(N-1) — under ~13 passages the vector leg can never
fire. The recovery corpus is >=14 passages so the vector path is exercised; a
separate tiny corpus proves the fail-safe (neither leg reaches its floor ->
explore, never a low-confidence hit).
"""

import re
from collections.abc import Iterator

import pytest

from hrono.cluster.blend import path_body, register_path_bodies
from hrono.db.database import Database
from hrono.embed.store import upsert_vector
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from hrono.recall import fts
from hrono.recall.engine import recall

MODEL = "emb"
DIMS = 8
PATH = "src/x.py"


def unit(index: int) -> list[float]:
    vec = [0.0] * DIMS
    vec[index] = 1.0
    return vec


def const_encode(vec: list[float]):
    def encode(texts: list[str]) -> list[list[float]]:
        return [vec for _ in texts]

    return encode


def add_passage(conn: object, body: bytes, content_vec: list[float]) -> str:
    digest = content_hash(body)
    upsert_content(conn, digest, body)  # type: ignore[arg-type]
    upsert_vector(conn, digest, MODEL, content_vec)  # type: ignore[arg-type]
    section_id = insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "ex/repo", PATH, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )
    uri = f"git://ex/repo/{PATH}@v1"
    conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO passages(section_id, source, source_type, instance, path, "
        "version, uri, byte_start, byte_end, content_hash, sp_paths, ordinal, "
        "created_at) VALUES (?, 'repo', 'git', 'ex/repo', ?, 'v1', ?, 0, ?, ?, "
        "'[]', 0, 't')",
        (section_id, PATH, uri, len(body), digest),
    )
    fts.index_passage(  # production indexes every passage; so must a fixture
        conn,  # type: ignore[arg-type]
        passage_id=int(
            conn.execute("SELECT MAX(id) FROM passages").fetchone()[0]
        ),
        source="repo",
        path=PATH,
        body=body.decode(),
    )
    return uri


def _plant_paths(conn: object) -> None:
    register_path_bodies(conn, [PATH])
    upsert_vector(conn, content_hash(path_body(PATH)), MODEL, unit(2))


@pytest.fixture
def big(tmp_path: object) -> Iterator[tuple[Database, str]]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        _plant_paths(conn)
        answer = add_passage(
            conn, b"the authentication flow issues bearer tokens\n", unit(0)
        )
        for i in range(15):  # >= 14 others so the vector leg can qualify one
            add_passage(conn, f"unrelated topic {i}\n".encode(), unit(1))
    yield database, answer
    database.close()


def test_planted_answer_is_recovered_above_the_floors(
    big: tuple[Database, str],
) -> None:
    database, answer = big
    with database.connect() as conn:
        # the question embeds to the answer's content vector (e0)
        result = recall(conn, "authentication?", MODEL, const_encode(unit(0)))
    assert result.message is None
    assert result.hits
    assert result.hits[0].uri == answer
    assert result.hits[0].kind == "source"


def test_a_no_answer_question_returns_the_explore_message(
    big: tuple[Database, str],
) -> None:
    database, _ = big
    with database.connect() as conn:
        # the question embeds orthogonal to every passage (e3) -> no qualifier
        result = recall(conn, "unrelated?", MODEL, const_encode(unit(3)))
    assert result.hits == ()
    assert result.message == "no confident matches - explore the map."


def test_tiny_corpus_fails_safe_to_explore(tmp_path: object) -> None:
    # under ~13 passages the vector leg cannot reach z>=3.5 and the keyword leg
    # cannot reach z>=6.0, so even a matching question returns explore, never a
    # low-confidence hit.
    database = Database.at(tmp_path / "tiny.db")
    with database.connect() as conn, conn:
        _plant_paths(conn)
        add_passage(conn, b"authentication tokens here\n", unit(0))
        add_passage(conn, b"other one\n", unit(1))
        add_passage(conn, b"other two\n", unit(1))
    try:
        with database.connect() as conn:
            result = recall(
                conn, "authentication?", MODEL, const_encode(unit(0))
            )
        assert result.hits == ()
        assert result.message == "no confident matches - explore the map."
    finally:
        database.close()


def _blend(content: list[float]) -> list[float]:
    norm = sum(v * v for v in content) ** 0.5
    return [v / norm for v in content]


@pytest.fixture
def rich(tmp_path: object) -> Iterator[Database]:
    """A corpus that genuinely holds MANY answers, plus a varied noise body.

    The shape the old estimator broke (#102): 12 real matches raise the mean
    AND the standard deviation they are then measured against, so every one of
    them scores under the floor. The noise scores vary slightly so the MAD is
    not degenerate — a flat noise body is the case ``_spread`` falls back on.
    """
    database = Database.at(tmp_path / "rich.db")
    with database.connect() as conn, conn:
        _plant_paths(conn)
        for i in range(12):  # strong matches, 0.80 .. 0.99 cosine
            content = _blend(
                [0.99 - i * 0.017, 0.14 + i * 0.05, 0.0] + [0.0] * (DIMS - 3)
            )
            add_passage(conn, f"the answer, phrasing {i}\n".encode(), content)
        for i in range(30):  # noise, slightly varied so the MAD is non-zero
            content = _blend([0.01 * i, 1.0, 0.0] + [0.0] * (DIMS - 3))
            add_passage(conn, f"unrelated topic {i}\n".encode(), content)
    yield database
    database.close()


def test_an_on_topic_question_fills_the_window(rich: Database) -> None:
    # the second half of #102's acceptance: a corpus with many genuine matches
    # must return a full window, not the 1-2 the old mean/sd estimator left.
    with rich.connect() as conn:
        result = recall(conn, "the answer?", MODEL, const_encode(unit(0)))
    assert result.message is None
    assert len(result.hits) == 10  # the cap, not the floor, is what bounds it
    assert all(hit.kind == "source" for hit in result.hits)


def test_an_off_topic_question_still_explores(rich: Database) -> None:
    # ... without letting the other half slip: the same corpus must still
    # refuse a question it has no answer for.
    with rich.connect() as conn:
        result = recall(conn, "nothing like it?", MODEL, const_encode(unit(3)))
    assert result.hits == ()
    assert result.message == "no confident matches - explore the map."


ABSENT = (
    "how to train a labrador puppy",
    "what is the capital of Peru",
    "recipes for a chocolate cake",
    "who won the 1998 world cup final",
    "symptoms of vitamin D deficiency",
    "best hiking trails in the Alps",
    "how do I tune a violin",
    "the plot of Anna Karenina",
)
PRESENT = "the bearer token authentication flow"

# a toy embedding with the property real ones have: text that shares words is
# near. Function words are IN the vocabulary on purpose — that is how an absent
# question ends up near a passage it has nothing to do with, which is the leak
# #102 introduced and this suite exists to catch.
_VOCAB = (
    "how",
    "to",
    "the",
    "a",
    "token",
    "authentication",
    "bearer",
    "licence",
)


def bag_encode(texts: list[str]) -> list[list[float]]:
    out = []
    for text in texts:
        terms = re.findall(r"[a-z0-9]+", text.lower())
        vec = [float(terms.count(word)) for word in _VOCAB]
        norm = sum(v * v for v in vec) ** 0.5
        out.append([v / norm for v in vec] if norm else vec)
    return out


def _bag(text: str) -> list[float]:
    return bag_encode([text])[0]


@pytest.fixture
def corpus(tmp_path: object) -> Iterator[Database]:
    """One subject, a bulk of other material, and a few generic passages.

    The generic ones share only FUNCTION words with an absent question, which
    is exactly how "how to train a labrador puppy" reached chalk's
    benchmark.js: the fixture has to be able to leak before the test can prove
    it does not.
    """
    database = Database.at(tmp_path / "corpus.db")
    with database.connect() as conn, conn:
        _plant_paths(conn)
        for i in range(3):
            body = f"bearer token authentication {'bearer ' * (i % 3)}{i}\n"
            add_passage(conn, body.encode(), _bag(body))
        for i in range(36):
            body = f"licence clause {i} licence licence licence\n"
            add_passage(conn, body.encode(), _bag(body))
        for i in range(3):
            body = f"how to how to a the thing {i}\n"
            add_passage(conn, body.encode(), _bag(body))
    yield database
    database.close()


def test_every_absent_question_returns_the_explore_message(
    corpus: Database,
) -> None:
    # ONE leak anywhere fails: seven of qa's eight absent questions held under
    # the plain floor and the eighth did not, so a single probe proves nothing.
    leaked = {}
    for question in ABSENT:
        with corpus.connect() as conn:
            result = recall(conn, question, MODEL, bag_encode)
        if result.hits:
            leaked[question] = len(result.hits)
    assert leaked == {}


def test_the_absent_questions_could_have_leaked(corpus: Database) -> None:
    # the suite above is only worth having if the corpus can leak: without
    # corroboration these questions DO clear the vector floor, on passages that
    # share nothing with them but function words.
    from hrono.recall import vector_leg

    reachable = 0
    for question in ABSENT:
        with corpus.connect() as conn:
            z = vector_leg.scores(conn, _bag(question), MODEL)
        reachable += sum(
            1 for score in z.values() if score >= vector_leg.Z_FLOOR
        )
    assert reachable > 0


def test_a_present_question_still_returns_hits(corpus: Database) -> None:
    # the counterweight, in the same suite ON PURPOSE: without it the cheapest
    # way to pass the test above is to raise the floor until everything is cut,
    # which restores the defect #102 exists to fix. Direction, not magnitude.
    with corpus.connect() as conn:
        result = recall(conn, PRESENT, MODEL, bag_encode)
    assert result.message is None
    assert result.hits


def test_the_present_question_mean_sd_got_wrong_is_recovered(
    rich: Database,
) -> None:
    # the estimator's own regression: this shape returns ZERO candidates under
    # mean/sd, so the suite fails if the median/MAD change is reverted.
    with rich.connect() as conn:
        result = recall(conn, "the answer?", MODEL, const_encode(unit(0)))
    assert result.message is None
    assert result.hits


def _add_at(conn: object, path: str, body: bytes, vec: list[float]) -> str:
    """A passage under its OWN document, so the window can diversify."""
    digest = content_hash(body)
    upsert_content(conn, digest, body)  # type: ignore[arg-type]
    upsert_vector(conn, digest, MODEL, vec)  # type: ignore[arg-type]
    section_id = insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "ex/repo", path, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )
    ordinal = int(
        conn.execute(  # type: ignore[attr-defined]
            "SELECT COUNT(*) FROM passages WHERE path = ?", (path,)
        ).fetchone()[0]
    )
    uri = f"git://ex/repo/{path}@v1#chunk-{ordinal}"
    conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO passages(section_id, source, source_type, instance, path, "
        "version, uri, byte_start, byte_end, content_hash, sp_paths, ordinal, "
        "created_at) VALUES (?, 'repo', 'git', 'ex/repo', ?, 'v1', ?, 0, ?, ?, "
        "'[]', ?, 't')",
        (section_id, path, uri, len(body), digest, ordinal),
    )
    fts.index_passage(
        conn,  # type: ignore[arg-type]
        passage_id=int(
            conn.execute("SELECT MAX(id) FROM passages").fetchone()[0]
        ),
        source="repo",
        path=path,
        body=body.decode(),
    )
    return uri


def test_recall_lets_a_second_document_into_a_dominated_window(
    tmp_path: object,
) -> None:
    # #126 end to end. The hog answers TWELVE times and scores higher every
    # time; the quiet document answers once, slightly worse. In pure score
    # order the window is ten hog hits and the quiet document never appears —
    # so this test fails if the reserve is not wired in, and fails again if the
    # document is taken to be the passage rather than the FILE (then every hit
    # is its own document and nothing is ever held back).
    database = Database.at(tmp_path / "hrono.db")
    try:
        with database.connect() as conn, conn:
            register_path_bodies(conn, ["src/hog.py", "docs/other.md"])
            for path in ("src/hog.py", "docs/other.md"):
                upsert_vector(
                    conn, content_hash(path_body(path)), MODEL, unit(2)
                )
            for i in range(12):
                _add_at(
                    conn,
                    "src/hog.py",
                    f"bearer token flow {i}\n".encode(),
                    unit(0),
                )
            weaker = [0.94, 0.0, 0.0, 0.34, 0.0, 0.0, 0.0, 0.0]
            quiet = _add_at(
                conn,
                "docs/other.md",
                b"bearer token flow, documented\n",
                weaker,
            )
            # noise sized from the estimator's own arithmetic: with n identical
            # strong passages in a corpus of N the best reachable z is
            # ~sqrt(N/n - 1), so thirteen strong hits need N > 146 to clear a
            # floor of 3.2 at all (#102). This test is about the window, not
            # the floor.
            for i in range(150):
                _add_at(
                    conn, "src/hog.py", f"unrelated {i}\n".encode(), unit(1)
                )

        with database.connect() as conn:
            result = recall(conn, "bearer?", MODEL, const_encode(unit(0)))

        documents = {hit.uri.split("#")[0] for hit in result.hits}
        assert len(result.hits) == 10  # a full window, not a truncated one
        assert quiet.split("#")[0] in documents  # the quiet document got in
        assert len(documents) == 2
    finally:
        database.close()
