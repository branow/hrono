from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.ingest import store
from hrono.ingest.identity import Address, content_hash


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    yield database
    database.close()


def test_identical_bytes_store_one_content_row(db: Database) -> None:
    body = b"def f():\n    return 1\n"
    other = b"def g():\n    return 2\n"
    with db.connect() as conn, conn:
        store.upsert_content(conn, content_hash(body), body)
        store.upsert_content(conn, content_hash(body), body)  # dedup no-op
        store.upsert_content(conn, content_hash(other), other)
    with db.connect() as conn:
        assert store.content_count(conn) == 2
        assert store.get_content(conn, content_hash(body)) == body


def test_a_section_reassembles_byte_identically_from_storage(
    db: Database,
) -> None:
    raw = b"alpha beta gamma delta epsilon zeta eta theta iota kappa\n"
    address = Address("git", "h/o/r", "f.txt", "v1")
    # two passages that tile the section [0, len)
    cut = 20
    ranges = ((0, cut), (cut, len(raw)))
    with db.connect() as conn, conn:
        section_hash = content_hash(raw)
        store.upsert_content(conn, section_hash, raw)
        section_id = store.insert_section(
            conn,
            source="r",
            address=address,
            start=0,
            end=len(raw),
            content_hash=section_hash,
            ordinal=0,
        )
        for ordinal, (start, end) in enumerate(ranges):
            body = raw[start:end]
            store.upsert_content(conn, content_hash(body), body)
            store.insert_passage(
                conn,
                section_id=section_id,
                source="r",
                address=address,
                start=start,
                end=end,
                content_hash=content_hash(body),
                sp_paths=("sp:/.~line",),
                ordinal=ordinal,
            )
    # read back FROM STORAGE and reassemble
    with db.connect() as conn:
        section = store.list_sections(conn, "r")[0]
        passages = store.list_passages(conn, section["id"])
        rebuilt = b"".join(
            store.get_content(conn, p["content_hash"]) for p in passages
        )
        assert rebuilt == store.get_content(conn, section["content_hash"])
        assert rebuilt == raw


def test_a_section_is_addressable_by_its_uri(db: Database) -> None:
    address = Address("git", "github.com/a/b", "src/x.py", "abc")
    body = b"x = 1\n"
    with db.connect() as conn, conn:
        store.upsert_content(conn, content_hash(body), body)
        store.insert_section(
            conn,
            source="b",
            address=address,
            start=0,
            end=len(body),
            content_hash=content_hash(body),
            ordinal=0,
        )
    with db.connect() as conn:
        found = store.section_by_uri(conn, address.uri)
        assert len(found) == 1
        assert found[0]["path"] == "src/x.py"
        assert found[0]["version"] == "abc"


def test_clearing_a_source_removes_its_sections_and_passages(
    db: Database,
) -> None:
    address = Address("git", "h/o/r", "f.py", "v1")
    body = b"kept body bytes here\n"
    with db.connect() as conn, conn:
        store.upsert_content(conn, content_hash(body), body)
        section_id = store.insert_section(
            conn,
            source="r",
            address=address,
            start=0,
            end=len(body),
            content_hash=content_hash(body),
            ordinal=0,
        )
        store.insert_passage(
            conn,
            section_id=section_id,
            source="r",
            address=address,
            start=0,
            end=len(body),
            content_hash=content_hash(body),
            sp_paths=("sp:/",),
            ordinal=0,
        )
    with db.connect() as conn, conn:
        store.clear_source(conn, "r")
    with db.connect() as conn:
        assert store.list_sections(conn, "r") == ()
        # passages cascaded away; the shared body is retained
        assert conn.execute("SELECT COUNT(*) FROM passages").fetchone()[0] == 0
        assert store.get_content(conn, content_hash(body)) == body
