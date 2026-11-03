"""A source whose url was edited is fetched from the new url."""

import subprocess
from pathlib import Path

import pytest

from hrono.ingest import SyncError
from hrono.ingest.git_syncer import git_sync
from tests.server.repo import commit, head_of, make_repo


def test_an_edited_url_is_fetched_without_touching_the_cache(
    tmp_path: Path,
) -> None:
    first = make_repo(tmp_path / "first")
    cache = tmp_path / "cache" / "flask"
    config = {"name": "flask", "url": str(first), "auth": None}
    assert git_sync(config, cache, 30) == head_of(first)

    # the registry's url now names a clone that carries one more commit
    second = tmp_path / "second"
    subprocess.run(
        ["git", "clone", "-q", str(first), str(second)],
        check=True,
        capture_output=True,
    )
    new = commit(second, "two")

    assert git_sync({**config, "url": str(second)}, cache, 30) == new
    assert (cache / "two.md").exists()


def test_a_url_that_looks_like_an_option_is_never_run_as_one(
    tmp_path: Path,
) -> None:
    # written straight to the registry, past the validation of the form
    cache = tmp_path / "cache" / "flask"
    config = {"name": "flask", "url": str(make_repo(tmp_path / "first"))}
    git_sync({**config, "auth": None}, cache, 30)
    marker = tmp_path / "x"

    with pytest.raises(SyncError):
        git_sync(
            {**config, "url": f"--upload-pack=touch {marker}", "auth": None},
            cache,
            30,
        )

    assert not marker.exists()
    # the url was stored as a url, never parsed as an option
    stored = subprocess.run(
        ["git", "-C", str(cache), "config", "remote.origin.url"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert stored.startswith("--upload-pack=")
