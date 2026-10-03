"""#215: asking a remote where it is, against a real repository."""

from __future__ import annotations

from pathlib import Path

from hrono.ingest.remote_head import remote_head
from tests.server.repo import commit, head_of, make_empty_repo, make_repo


def _config(url: object) -> dict[str, object]:
    return {"name": "r", "type": "git", "url": str(url), "auth": None}


def test_it_returns_the_commit_the_remote_is_at(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "r")

    assert remote_head(_config(repo), 10.0) == head_of(repo)


def test_it_follows_the_remote_when_it_moves(tmp_path: Path) -> None:
    repo = make_repo(tmp_path / "r")
    before = remote_head(_config(repo), 10.0)

    moved = commit(repo, "two")

    assert remote_head(_config(repo), 10.0) == moved != before


def test_a_remote_that_is_not_there_is_not_known(tmp_path: Path) -> None:
    assert remote_head(_config(tmp_path / "missing"), 10.0) is None


def test_a_repository_with_no_commits_is_not_known(tmp_path: Path) -> None:
    empty = make_empty_repo(tmp_path / "empty")

    assert remote_head(_config(empty), 10.0) is None


def test_a_remote_that_does_not_answer_in_time_is_not_known(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path / "r")

    assert remote_head(_config(repo), 0.0001) is None
