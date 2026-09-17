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
    assert Z_FLOOR == 3.5
