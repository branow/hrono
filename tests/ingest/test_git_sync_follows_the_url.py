"""A source whose url was edited is fetched from the new url."""

import subprocess
from pathlib import Path

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
