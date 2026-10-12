"""The recall recipe end to end: gate, cosine order, one passage per document.

Vectors are planted, so a test says exactly which passage is closest to the
question; the words of the question decide the gate.
"""

from collections.abc import Iterator

import pytest

from hrono.db.database import Database
from hrono.embed.store import upsert_vector
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from hrono.recall import fts
from hrono.recall.engine import recall
from hrono.recall.window import CAP, EXPLORE_MESSAGE

MODEL = "emb"
DIMS = 8


def unit(
    index: int, other: int | None = None, weight: float = 0.0
) -> list[float]:
    vec = [0.0] * DIMS
    vec[index] = 1.0
    if other is not None:
        vec[other] = weight
    return vec


def const_encode(vec: list[float]):
    def encode(texts: list[str]) -> list[list[float]]:
        return [vec for _ in texts]

    return encode


def add_passage(
    conn: object,
    body: bytes,
    vec: list[float],
    path: str = "src/x.py",
    *,
    source: str = "repo",
    kind: str = "git",
    ordinal: int = 0,
) -> str:
    """A passage the way split stores one: section, passage row, FTS row."""
    digest = content_hash(body)
    upsert_content(conn, digest, body)  # type: ignore[arg-type]
    upsert_vector(conn, digest, MODEL, vec)  # type: ignore[arg-type]
    instance = "hrono" if kind == "node" else "ex/repo"
    version = "sig" if kind == "node" else "v1"
    section_id = insert_section(
        conn,  # type: ignore[arg-type]
        source=source,
        address=Address(kind, instance, path, version),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=ordinal,
    )
    uri = f"{kind}://{instance}/{path}@{version}"
    conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO passages(section_id, source, source_type, instance, path, "
        "version, uri, byte_start, byte_end, content_hash, sp_paths, ordinal, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, '[]', ?, 't')",
        (
            section_id,
            source,
            kind,
            instance,
            path,
            version,
            uri,
            len(body),
            digest,
            ordinal,
        ),
    )
    fts.index_passage(
        conn,  # type: ignore[arg-type]
        passage_id=int(
            conn.execute("SELECT MAX(id) FROM passages").fetchone()[0]
        ),
        source=source,
        path=path,
        body=body.decode(),
    )
    return uri


@pytest.fixture
def corpus(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        add_passage(
            conn,
            b"the authentication flow issues bearer tokens\n",
            unit(0),
            "src/auth.py",
        )
        add_passage(
            conn,
            b"bearer tokens are refreshed before they expire\n",
            unit(0, 1, 0.5),
            "src/refresh.py",
        )
        for i in range(6):
            add_passage(
                conn,
                f"invoice ledger entry {i}\n".encode(),
                unit(1),
                f"src/ledger_{i}.py",
            )
    yield database
    database.close()


def ask(database: Database, question: str, vec: list[float], limit: int = CAP):
    with database.connect() as conn:
        return recall(conn, question, MODEL, const_encode(vec), limit=limit)


def test_the_closest_passage_comes_first(corpus: Database) -> None:
    result = ask(corpus, "How are bearer tokens issued?", unit(0))

    assert result.message is None
    assert [hit.path for hit in result.hits[:2]] == [
        "src/auth.py",
        "src/refresh.py",
    ]
    assert result.hits[0].score == pytest.approx(1.0)
    assert result.hits[0].kind == "source"


def test_a_question_the_tree_has_no_words_for_is_sent_to_the_map(
    corpus: Database,
) -> None:
    # its vector is the answer's own: only the gate can stop it
    result = ask(corpus, "What hydration suits a sourdough starter?", unit(0))

    assert result.hits == ()
    assert result.message == EXPLORE_MESSAGE


def test_a_question_with_no_content_words_is_sent_to_the_map(
    corpus: Database,
) -> None:
    assert ask(corpus, "How is it?", unit(0)).message == EXPLORE_MESSAGE


def test_a_small_tree_answers_without_a_floor(tmp_path: object) -> None:
    database = Database.at(tmp_path / "hrono.db")
    try:
        with database.connect() as conn, conn:
            answer = add_passage(conn, b"bearer tokens\n", unit(0))

        result = ask(database, "bearer tokens?", unit(0))

        assert [hit.uri for hit in result.hits] == [answer]
    finally:
        database.close()


def test_one_file_gives_one_passage(tmp_path: object) -> None:
    database = Database.at(tmp_path / "hrono.db")
    try:
        with database.connect() as conn, conn:
            for i in range(3):  # three slices of one file, all closest
                add_passage(
                    conn,
                    f"bearer token rule {i}\n".encode(),
                    unit(0),
                    ordinal=i,
                )
            add_passage(
                conn, b"bearer token notes\n", unit(0, 1, 1.0), "doc.md"
            )

        result = ask(database, "bearer token rules?", unit(0))

        assert [hit.path for hit in result.hits] == ["src/x.py", "doc.md"]
    finally:
        database.close()


def test_the_window_is_never_padded(corpus: Database) -> None:
    result = ask(corpus, "bearer tokens?", unit(0), limit=CAP)

    assert len(result.hits) == 8  # every file once, nothing invented


def test_the_window_holds_at_most_the_limit(corpus: Database) -> None:
    assert len(ask(corpus, "bearer tokens?", unit(0), limit=3).hits) == 3
    assert len(ask(corpus, "bearer tokens?", unit(0), limit=50).hits) <= CAP


def test_a_brief_competes_with_the_sources(corpus: Database) -> None:
    # an overview question is closest to a brief, and the brief wins: nothing
    # about being a summary holds a passage back
    with corpus.connect() as conn, conn:
        brief = add_passage(
            conn,
            b"overview: authentication signs and verifies bearer tokens\n",
            unit(3),
            "nodes/1/auth",
            source="node-1",
            kind="node",
        )

    result = ask(corpus, "An overview of authentication?", unit(3))

    assert result.hits[0].uri == brief
    assert result.hits[0].kind == "summary"
