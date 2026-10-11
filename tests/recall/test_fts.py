"""The FTS5 index over passage path + body, kept in sync by split."""

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.ingest.split_op import split_source
from hrono.ingest.sync import sync
from hrono.jobs.model import Job
from hrono.recall import fts
from hrono.registry import store as registry_store
from tests.context import job_context
from tests.repo_template import memoized


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True
    )


@memoized
def make_repo(path: Path, files: dict[str, str]) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "Test")
    for name, content in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "first")
    return path.as_uri()


def register(conn: object, url: str) -> None:
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "sources",
        "repo",
        json.dumps({"name": "repo", "type": "git", "url": url, "auth": {}}),
        None,
        "t",
    )


def _job(op: str) -> Job:
    return Job(
        id="j",
        parent_id=None,
        tree=None,
        op=op,
        scope={"type": "source", "name": "repo"},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


FILES = {
    "auth/login.py": "def authenticate(user):\n    return verify(user)\n",
    "docs/guide.md": "# Guide\n\nThe widget subsystem handles rendering.\n",
}


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.chdir(tmp_path)
    remote = tmp_path / "remote"
    make_repo(remote, FILES)
    yield remote


@pytest.fixture
def db(repo: Path, tmp_path: Path) -> Iterator[Database]:
    url = repo.as_uri()
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn:
        register(conn, url)
    sync(_job("sync"), job_context(database, tmp_path))
    split_source(_job("split"), job_context(database, tmp_path))
    yield database
    database.close()


def _passage_count(db: Database) -> int:
    with db.connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM passages").fetchone()[0])


def _fts_count(db: Database) -> int:
    with db.connect() as conn:
        return int(
            conn.execute("SELECT COUNT(*) FROM passages_fts").fetchone()[0]
        )


def test_index_has_one_row_per_passage(db: Database) -> None:
    assert _fts_count(db) == _passage_count(db) >= 2


def test_body_terms_match_and_are_bm25_ranked(db: Database) -> None:
    with db.connect() as conn:
        hits = fts.search(conn, "widget OR authenticate")
    assert hits  # OR-ed terms return matches
    scores = [score for _, score in hits]
    assert scores == sorted(scores)  # best (lowest bm25) first


def test_path_terms_are_indexed(db: Database) -> None:
    # "login" appears only in the path auth/login.py, not the body -> path is
    # indexed.
    with db.connect() as conn:
        assert fts.search(conn, "login")


def test_resplit_is_consistent_no_duplicate_rows(
    db: Database, tmp_path: Path
) -> None:
    split_source(_job("split"), job_context(db, tmp_path))  # re-split unchanged
    assert _fts_count(db) == _passage_count(db)  # rebuilt, not duplicated


def test_changed_and_removed_files_leave_no_orphans(
    db: Database, repo: Path, tmp_path: Path
) -> None:
    # remove the docs file, change the auth file, re-sync + re-split
    (repo / "docs" / "guide.md").unlink()
    (repo / "auth" / "login.py").write_text("def logout(user):\n    pass\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-qm", "change")
    sync(_job("sync"), job_context(db, tmp_path))
    split_source(_job("split"), job_context(db, tmp_path))
    assert _fts_count(db) == _passage_count(
        db
    )  # no orphans after change/remove
    with db.connect() as conn:
        assert not fts.search(conn, "widget")  # removed body term is gone
        assert fts.search(conn, "logout")  # new body term is present
