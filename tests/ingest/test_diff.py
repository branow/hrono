"""T33: content-hash file diff classification for incremental update."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.ingest import store as istore
from hrono.ingest.diff import (
    Change,
    classify,
    current_files,
    diff,
    stored_files,
)
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.readers import READERS


def test_new_changed_deleted_unchanged() -> None:
    old = {"keep.py": "h1", "change.py": "h2", "gone.py": "h3"}
    new = {"keep.py": "h1", "change.py": "h2new", "add.py": "h4"}
    changes = set(classify(old, new))
    assert Change("add.py", "new") in changes
    assert Change("change.py", "changed") in changes
    assert Change("gone.py", "deleted") in changes
    assert not any(c.path == "keep.py" for c in changes)  # unchanged -> silent


def test_move_is_detected_with_old_path() -> None:
    # same content hash, different path -> moved (not delete+new)
    old = {"src/old.py": "same"}
    new = {"src/new.py": "same"}
    changes = classify(old, new)
    assert changes == (Change("src/new.py", "moved", old_path="src/old.py"),)


def test_first_sync_is_all_new() -> None:
    new = {"a.py": "h1", "b.py": "h2"}
    assert set(classify({}, new)) == {
        Change("a.py", "new"),
        Change("b.py", "new"),
    }


def test_no_op_resync_classifies_nothing() -> None:
    files = {"a.py": "h1", "b.py": "h2"}
    assert classify(files, files) == ()


def test_deterministic_order() -> None:
    old = {"x": "1"}
    new = {"y": "2", "z": "3"}
    assert classify(old, new) == classify(old, new)


@pytest.fixture
def cache(tmp_path: Path) -> Path:
    root = tmp_path / "cache"
    root.mkdir()
    (root / "a.py").write_text("alpha bytes\n")
    (root / "b.py").write_text("beta bytes\n")
    (root / "skip.log").write_text("noise\n")
    return root


def test_current_files_honours_the_filter(cache: Path) -> None:
    files = current_files(
        READERS["git"], {"filter": {"exclude": ["*.log"]}}, cache
    )
    assert set(files) == {"a.py", "b.py"}  # skip.log excluded -> absent
    assert files["a.py"] == content_hash(b"alpha bytes\n")


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    yield database
    database.close()


def _store_file(db: Database, path: str, chunks: list[bytes]) -> None:
    """Store a file as tiling sections (concat == the file bytes)."""
    with db.connect() as conn, conn:
        start = 0
        for ordinal, chunk in enumerate(chunks):
            istore.upsert_content(conn, content_hash(chunk), chunk)
            istore.insert_section(
                conn,
                source="repo",
                address=Address("git", "ex/repo", path, "v1"),
                start=start,
                end=start + len(chunk),
                content_hash=content_hash(chunk),
                ordinal=ordinal,
            )
            start += len(chunk)


def test_stored_files_reconstructs_the_file_hash(db: Database) -> None:
    _store_file(db, "a.py", [b"AL", b"PHA"])  # tiles to "ALPHA"
    with db.connect() as conn:
        stored = stored_files(conn, "repo")
    assert stored == {"a.py": content_hash(b"ALPHA")}


def test_diff_end_to_end(db: Database, tmp_path: Path) -> None:
    _store_file(db, "a.py", [b"AL", b"PHA"])  # stored version: a.py = "ALPHA"
    _store_file(db, "old.py", [b"MOVED"])  # will be renamed unchanged
    root = tmp_path / "cache"
    root.mkdir()
    (root / "a.py").write_text("ALPHA")  # unchanged
    (root / "new.py").write_text("MOVED")  # same bytes as old.py -> moved
    (root / "added.py").write_text("brand new")  # new
    with db.connect() as conn:
        changes = set(diff(conn, "repo", READERS["git"], {}, root))
    assert Change("new.py", "moved", old_path="old.py") in changes
    assert Change("added.py", "new") in changes
    assert not any(c.path == "a.py" for c in changes)  # unchanged, silent
