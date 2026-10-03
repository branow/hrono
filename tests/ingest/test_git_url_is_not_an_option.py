"""A git source URL never reaches git as an option (E020)."""

import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from hrono.ingest.git_syncer import git_sync
from hrono.ingest.remote_head import remote_head
from hrono.registry.collections.sources import GitSource
from hrono.registry.descriptor import ValidationFailed
from hrono.registry.validation.git_validation import validate_git

_GIT = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
}


def _repo_named(parent: Path, name: str) -> Path:
    repo = parent / name
    repo.mkdir()
    (repo / "a.md").write_text("# a\n")
    for args in (["init", "-q"], ["add", "a.md"], ["commit", "-q", "-m", "x"]):
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            env={**_GIT, "PATH": "/usr/bin:/bin:/usr/local/bin"},
        )
    return repo


@pytest.mark.parametrize("url", ["--upload-pack=touch /tmp/x", "-x", " -x"])
def test_the_model_refuses_a_url_that_starts_with_a_dash(url: str) -> None:
    with pytest.raises(ValidationError, match="url"):
        GitSource(
            name="r",
            type="git",
            url=url,
            auth={"method": "none"},  # type: ignore[arg-type]
        )


def test_a_dash_inside_a_url_is_fine() -> None:
    source = GitSource(
        name="r",
        type="git",
        url="https://example.com/my-repo.git",
        auth={"method": "none"},  # type: ignore[arg-type]
    )
    assert source.url.endswith("my-repo.git")


def _clone_to_work_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # git runs `--upload-pack=...` from a clone's directory, as it would for
    # a url that is an option, so the marker proves whether it was run.
    repo = _repo_named(tmp_path, "r")
    work = tmp_path / "work"
    subprocess.run(["git", "clone", "-q", str(repo), str(work)], check=True)
    monkeypatch.chdir(work)


def test_validate_git_does_not_run_a_url_that_is_an_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clone_to_work_in(tmp_path, monkeypatch)
    marker = tmp_path / "marker"
    with pytest.raises(ValidationFailed):
        validate_git(
            {
                "url": f"--upload-pack=touch {marker}",
                "auth": {"method": "none"},
            }
        )
    assert not marker.exists()


def test_remote_head_does_not_run_a_url_that_is_an_option(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _clone_to_work_in(tmp_path, monkeypatch)
    marker = tmp_path / "marker"
    config = {
        "url": f"--upload-pack=touch {marker}",
        "auth": {"method": "none"},
    }
    assert remote_head(config, 30.0) is None
    assert not marker.exists()


def test_ls_remote_of_an_ordinary_local_repo_still_works(
    tmp_path: Path,
) -> None:
    repo = _repo_named(tmp_path, "ok")
    config = {"url": str(repo), "auth": {"method": "none"}}
    validate_git(config)
    assert len(remote_head(config, 30.0) or "") == 40
    with pytest.raises(ValidationFailed):
        validate_git(
            {"url": str(tmp_path / "nope"), "auth": {"method": "none"}}
        )


def test_clone_ends_options_before_the_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _repo_named(tmp_path, "-odd")
    monkeypatch.chdir(tmp_path)
    sha = git_sync(
        {"name": "r", "url": "-odd", "auth": {"method": "none"}},
        tmp_path / "cache" / "r",
        30.0,
    )
    assert len(sha) == 40
    assert (tmp_path / "cache" / "r" / "a.md").exists()
