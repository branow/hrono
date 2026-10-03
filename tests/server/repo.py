"""A real git repository for tests that need a remote that can move."""

from __future__ import annotations

import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=t",
            "-c",
            "user.email=t@t",
            "-C",
            str(repo),
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def make_repo(path: Path) -> Path:
    """A repository on `main` with one commit."""
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    commit(path, "one")
    return path


def commit(repo: Path, message: str) -> str:
    """Add a file and commit it; return the new HEAD."""
    (repo / f"{message}.md").write_text(f"{message}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", message)
    return head_of(repo)


def head_of(repo: Path) -> str:
    return _git(repo, "rev-parse", "HEAD")


def make_empty_repo(path: Path) -> Path:
    """A repository with nothing committed: it has no HEAD to report."""
    path.mkdir()
    _git(path, "init", "-q", "-b", "main")
    return path
