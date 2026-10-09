"""A git section's file on its host, at the commit it was read."""

from __future__ import annotations

from pathlib import Path

import pytest

from hrono.ingest.blob_link import blob_url
from hrono.ingest.git_reader import git_instance
from hrono.ingest.github import github_instance

SHA = "a1b2c3"


@pytest.mark.parametrize(
    ("instance", "path", "first", "last", "expected"),
    [
        pytest.param(
            "github.com/acme/repo",
            "docs/a b.md",
            3,
            9,
            f"https://github.com/acme/repo/blob/{SHA}/docs/a%20b.md#L3-L9",
            id="github-range",
        ),
        pytest.param(
            "github.com/acme/repo",
            "a.md",
            4,
            4,
            f"https://github.com/acme/repo/blob/{SHA}/a.md#L4",
            id="github-one-line",
        ),
        pytest.param(
            "github.com/acme",
            "repo/docs/a.md",
            1,
            2,
            f"https://github.com/acme/repo/blob/{SHA}/docs/a.md#L1-L2",
            id="discovery-owner-instance",
        ),
        pytest.param(
            "bitbucket.org/ws",
            "slug/a.md",
            5,
            8,
            f"https://bitbucket.org/ws/slug/src/{SHA}/a.md#lines-5:8",
            id="bitbucket-discovery",
        ),
        pytest.param(
            "gitlab.com/group/sub/repo",
            "a.md",
            5,
            8,
            f"https://gitlab.com/group/sub/repo/-/blob/{SHA}/a.md#L5-8",
            id="gitlab-subgroup",
        ),
        pytest.param(
            "git.internal/acme/repo", "a.md", 1, 2, None, id="unknown-host"
        ),
        pytest.param("github.com", "a.md", 1, 2, None, id="no-owner"),
        pytest.param(
            "gitlab.com/owner", "a.md", 1, 2, None, id="gitlab-owner-only"
        ),
        pytest.param(
            "gitlab.com/owner",
            "repo/a.md",
            1,
            2,
            f"https://gitlab.com/owner/repo/-/blob/{SHA}/a.md#L1-2",
            id="gitlab-owner-with-repo-in-path",
        ),
    ],
)
def test_the_link_is_the_hosts_blob_page_at_the_commit(
    instance: str, path: str, first: int, last: int, expected: str | None
) -> None:
    assert blob_url(instance, path, SHA, first, last) == expected


def test_a_url_with_credentials_yields_a_link_without_them() -> None:
    userinfo = "me:" + "s3cret"
    instance = git_instance(
        {"url": f"https://{userinfo}@github.com/acme/repo.git"}, Path()
    )

    link = blob_url(instance, "a.md", SHA, 1, 1)

    assert link == f"https://github.com/acme/repo/blob/{SHA}/a.md#L1"
    assert "s3cret" not in str(link)


def test_a_discovery_source_links_into_the_repo_it_found() -> None:
    instance = github_instance({"owner": "acme"}, Path())

    assert (
        blob_url(instance, "repo/x.md", SHA, 1, 1)
        == f"https://github.com/acme/repo/blob/{SHA}/x.md#L1"
    )
