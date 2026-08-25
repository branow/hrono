"""T28 calibration: a planted answer is recovered; a strict miss -> explore.

Sizing matters (#072 review): the vector leg z-scores over the query's own
distribution, so max z ~ sqrt(N-1) — under ~13 passages the vector leg can never
fire. The recovery corpus is >=14 passages so the vector path is exercised; a
separate tiny corpus proves the fail-safe (neither leg reaches its floor ->
explore, never a low-confidence hit).
"""

from collections.abc import Iterator

import pytest

from hrono.cluster.blend import path_body, register_path_bodies
from hrono.db.database import Database, open_database
from hrono.embed.store import upsert_vector
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
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
    return uri


def _plant_paths(conn: object) -> None:
    register_path_bodies(conn, [PATH])
    upsert_vector(conn, content_hash(path_body(PATH)), MODEL, unit(2))


@pytest.fixture
def big(tmp_path: object) -> Iterator[tuple[Database, str]]:
    database = Database(open_database(tmp_path / "hrono.db"))  # type: ignore[operator]
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
    database = Database(open_database(tmp_path / "tiny.db"))  # type: ignore[operator]
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
