"""The document key is the URI, because the URI carries no position.

`_documents` must not `split("#")` the URI on the belief that a passage is
addressed `...#chunk-3@v1`. Nothing emits that fragment: hrono has no named
fragments, since `@version` already changes every URI on any edit, and where a
passage sits lives in `ordinal` and `sp_paths`. Such a strip would be a no-op
that only looks like the rule it names — and would go on looking right if a
fragment ever DID appear, silently grouping by file when the code around it
assumes otherwise.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_passage, insert_section, upsert_content
from hrono.recall.engine import _documents

VERSION = "v1"


def _passage(conn: object, path: str, body: bytes, ordinal: int) -> int:
    address = Address("git", "ex/repo", path, VERSION)
    digest = content_hash(body)
    upsert_content(conn, digest, body)  # type: ignore[arg-type]
    section = insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=address,
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=ordinal,
    )
    return insert_passage(
        conn,  # type: ignore[arg-type]
        section_id=section,
        source="repo",
        address=address,
        start=0,
        end=len(body),
        content_hash=digest,
        sp_paths=(),
        ordinal=ordinal,
    )


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    yield database
    database.close()


def test_passages_of_one_file_share_a_document(db: Database) -> None:
    with db.connect() as conn, conn:
        first = _passage(conn, "src/x.py", b"the first slice\n", 0)
        second = _passage(conn, "src/x.py", b"the second slice\n", 1)
        other = _passage(conn, "src/y.py", b"a different file\n", 0)

    with db.connect() as conn:
        keys = _documents(conn, [first, second, other])

    assert keys[first] == keys[second]  # the file, not the slice
    assert keys[other] != keys[first]
    assert keys[first] == f"git://ex/repo/src/x.py@{VERSION}"


def test_the_key_is_the_stored_uri_untouched(db: Database) -> None:
    # the guard the strip was standing in for: the key must be whatever the
    # address renders, so a change to the URI scheme moves BOTH together
    # instead of leaving the key half-parsed.
    with db.connect() as conn, conn:
        passage = _passage(conn, "docs/a b.md", b"a path with a space\n", 0)

    with db.connect() as conn:
        stored = conn.execute(
            "SELECT uri FROM passages WHERE id = ?", (passage,)
        ).fetchone()["uri"]
        keys = _documents(conn, [passage])

    assert keys[passage] == stored
