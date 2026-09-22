"""T26.1: the vector leg qualifies near-duplicates at z >= 3.5, rejects rest."""

from collections.abc import Iterator

import pytest

from hrono.cluster.blend import path_body, register_path_bodies
from hrono.db.database import Database
from hrono.embed.store import upsert_vector
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from hrono.recall import fts
from hrono.recall.vector_leg import Z_FLOOR, search

MODEL = "emb"
DIMS = 8
PATH = "src/x.py"  # one shared path, embedded orthogonal to the query


def _unit(index: int) -> list[float]:
    vec = [0.0] * DIMS
    vec[index] = 1.0
    return vec


def add_passage(conn: object, body: bytes, content_vec: list[float]) -> int:
    upsert_content(conn, content_hash(body), body)  # type: ignore[arg-type]
    upsert_vector(conn, content_hash(body), MODEL, content_vec)  # type: ignore[arg-type]
    section_id = insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "ex/repo", PATH, "v1"),
        start=0,
        end=len(body),
        content_hash=content_hash(body),
        ordinal=0,
    )
    cursor = conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO passages(section_id, source, source_type, instance, path, "
        "version, uri, byte_start, byte_end, content_hash, sp_paths, ordinal, "
        "created_at) VALUES (?, 'repo', 'git', 'ex/repo', ?, 'v1', ?, 0, ?, ?, "
        "'[]', 0, 't')",
        (
            section_id,
            PATH,
            f"git://ex/repo/{PATH}@v1",
            len(body),
            content_hash(body),
        ),
    )
    passage_id = int(cursor.lastrowid)
    fts.index_passage(  # production indexes every passage; so must a fixture
        conn,  # type: ignore[arg-type]
        passage_id=passage_id,
        source="repo",
        path=PATH,
        body=body.decode(),
    )
    return passage_id


@pytest.fixture
def db(tmp_path: object) -> Iterator[tuple[Database, int]]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        register_path_bodies(conn, [PATH])
        upsert_vector(conn, content_hash(path_body(PATH)), MODEL, _unit(2))
        # one passage near-identical to the query (content e0)
        dup = add_passage(conn, b"the query itself\n", _unit(0))
        # many unrelated passages (content e1, orthogonal to the query)
        for i in range(20):
            add_passage(conn, f"unrelated body {i}\n".encode(), _unit(1))
    yield database, dup
    database.close()


def test_near_duplicate_qualifies_and_unrelated_do_not(
    db: tuple[Database, int],
) -> None:
    database, dup = db
    with database.connect() as conn:
        hits = search(conn, _unit(0), MODEL)  # query content = e0
    ids = [pid for pid, _ in hits]
    assert ids == [dup]  # only the near-duplicate clears z >= 3.5
    assert all(z >= Z_FLOOR for _, z in hits)


def test_empty_index_returns_no_hits(tmp_path: object) -> None:
    database = Database.at(tmp_path / "hrono.db")
    try:
        with database.connect() as conn:
            assert search(conn, _unit(0), MODEL) == ()
    finally:
        database.close()


def test_z_floor_is_baked() -> None:
    # swept across the paraphrase, corpus-vocabulary and absent suites (#134);
    # 3.5 left 4/6 paraphrases failing, 3.2 recovers all six and the eleven
    # absent questions are unchanged.
    assert Z_FLOOR == 3.2


def _plant(database: Database, *, noise_path_matches_query: bool) -> int:
    """A corpus whose answer is strong in one view and ordinary in the other.

    The blend is a per-passage average, so a passage only stands out blended
    when it beats the crowd THERE. When the crowd shares the query's path
    signal, the answer's content advantage is halved into the noise (#127's
    paraphrase case); when the crowd does not, a path-named answer is the only
    thing the path half can see (#127's `uuid/version7.go` case). Returns the
    planted answer's passage id.
    """
    answer_path = "src/answer.py"
    crowd_path = "docs/topic.md"
    with database.connect() as conn, conn:
        register_path_bodies(conn, [answer_path, crowd_path])
        # the query's own axis is e0; a path embedded on e0 matches the query
        upsert_vector(
            conn,
            content_hash(path_body(crowd_path)),
            MODEL,
            _unit(0) if noise_path_matches_query else _unit(3),
        )
        upsert_vector(
            conn,
            content_hash(path_body(answer_path)),
            MODEL,
            _unit(3) if noise_path_matches_query else _unit(0),
        )
        answer = add_passage(
            conn,
            b"the query itself\n"
            if noise_path_matches_query
            else b"nothing like the query\n",
            _unit(0) if noise_path_matches_query else _unit(1),
        )
        conn.execute(
            "UPDATE passages SET path = ? WHERE id = ?", (answer_path, answer)
        )
        for i in range(40):
            crowd = add_passage(conn, f"crowd body {i}\n".encode(), _unit(1))
            conn.execute(
                "UPDATE passages SET path = ? WHERE id = ?",
                (crowd_path, crowd),
            )
    return answer


def test_a_content_match_the_crowds_paths_drown_still_qualifies(
    tmp_path: object,
) -> None:
    # #127: half a passage's norm in the blend is its FILE PATH. When the crowd
    # shares the query's path signal, the answer's content advantage is halved
    # into that noise and it never clears the floor. Measured on the QA corpus,
    # "how do I style terminal output with colours" over a corpus holding the
    # whole of chalk: ONE passage cleared blended, SEVENTEEN content-only.
    database = Database.at(tmp_path / "hrono.db")
    try:
        answer = _plant(database, noise_path_matches_query=True)
        with database.connect() as conn:
            ids = [pid for pid, _ in search(conn, _unit(0), MODEL)]
        assert answer in ids
    finally:
        database.close()


def test_a_path_named_answer_still_qualifies(tmp_path: object) -> None:
    # the other shape, and why dropping the blend is not the fix: "generate a
    # version 7 uuid" went 10 hits to 1 content-only, because THAT question's
    # vocabulary lives in the path (`uuid/version7.go`). The answer here says
    # nothing like the query and is found only by where it lives.
    database = Database.at(tmp_path / "hrono.db")
    try:
        answer = _plant(database, noise_path_matches_query=False)
        with database.connect() as conn:
            ids = [pid for pid, _ in search(conn, _unit(0), MODEL)]
        assert answer in ids
    finally:
        database.close()
