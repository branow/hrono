"""A git source URL never reaches git as an option (E020)."""

import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from hrono.ingest.git_syncer import git_sync
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


def test_ls_remote_ends_options_before_the_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # git itself refuses a "-"-named path for ls-remote even after "--", so
    # the separator is pinned on the argv, and a real ls-remote of an ordinary
    # local repo proves the command still works with it.
    argv: list[list[str]] = []
    real_run = subprocess.run

    def spy(command: list[str], **kwargs: object):  # type: ignore[no-untyped-def]
        argv.append(command)
        return real_run(command, **kwargs)  # type: ignore[call-overload]

    monkeypatch.setattr(
        "hrono.registry.validation.git_validation.subprocess.run", spy
    )
    repo = _repo_named(tmp_path, "ok")
    argv.clear()
    validate_git({"url": str(repo), "auth": {"method": "none"}})
    assert argv[0][-2:] == ["--", str(repo)]
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
