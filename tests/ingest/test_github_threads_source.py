"""A github-threads source ingests a repository's conversations as pages.

These pin what a thread page says (state, posts, replies, reviews), the
``until`` cutoff that keeps a source pinned at a past date from reading the
future, cursor pagination of threads and of long comment lists, the per-post
cut, the errors, and the address a thread gets once split.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.ingest import SyncError
from hrono.ingest.github_threads import (
    API,
    github_threads_instance,
    pages,
    render,
    validate_github_threads,
)
from hrono.ingest.split_op import split_source
from hrono.ingest.sync import sync
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.registry import store as registry_store
from hrono.registry.descriptor import ValidationFailed

PLACEHOLDER = "g" * 12  # stands in for the token


def _config(**extra: object) -> dict:
    return {
        "name": "acme-threads",
        "type": "github-threads",
        "repo": "acme/payments",
        "auth": {"method": "token", "token": PLACEHOLDER},
        **extra,
    }


def _post(*answers: dict, status: int = 200):
    """A fake GraphQL endpoint: the answers in order, every request kept."""
    sent: list[dict] = []
    queue = list(answers)

    def post(url: str, headers: dict, body: dict, timeout: float):
        assert url == API
        sent.append({"headers": headers, **body})
        return status, (queue.pop(0) if queue else {"data": {}})

    post.sent = sent  # type: ignore[attr-defined]
    return post


def _page(*nodes: dict, after: str | None = None) -> dict:
    info = {"hasNextPage": after is not None, "endCursor": after}
    return {
        "data": {
            "repository": {"threads": {"pageInfo": info, "nodes": list(nodes)}}
        }
    }


def _comment(login: str, when: str, body: str, **extra: object) -> dict:
    return {
        "author": {"login": login},
        "createdAt": when,
        "body": body,
        **extra,
    }


def _issue(number: int, created: str, **extra: object) -> dict:
    return {
        "id": f"I{number}",
        "number": number,
        "title": f"Issue {number}",
        "createdAt": created,
        "closedAt": None,
        "author": {"login": "ann"},
        "body": "It breaks.",
        "labels": {"nodes": []},
        "comments": {"pageInfo": {"hasNextPage": False}, "nodes": []},
        **extra,
    }


def test_a_thread_page_has_its_facts_posts_and_replies_in_order() -> None:
    thread = _issue(
        7,
        "2026-01-02T10:00:00Z",
        closedAt="2026-01-05T09:00:00Z",
        stateReason="COMPLETED",
        labels={"nodes": [{"name": "bug"}]},
        comments={
            "nodes": [
                _comment("bob", "2026-01-04T00:00:00Z", "Second."),
                _comment("cy", "2026-01-03T00:00:00Z", "First."),
            ]
        },
    )

    text = render("issues", thread)

    assert text.startswith("# Issue #7: Issue 7\n")
    assert "- State: closed on 2026-01-05 (completed)" in text
    assert "- Opened by ann on 2026-01-02" in text
    assert "- Labels: bug" in text
    assert "It breaks." in text
    assert text.index("Comment by cy on 2026-01-03") < text.index(
        "Comment by bob on 2026-01-04"
    )


def test_until_drops_later_comments_and_reads_a_later_close_as_open() -> None:
    thread = _issue(
        7,
        "2026-01-02T10:00:00Z",
        closedAt="2026-03-01T00:00:00Z",
        comments={
            "nodes": [
                _comment("bob", "2026-01-04T00:00:00Z", "Before."),
                _comment("cy", "2026-02-27T08:00:00Z", "On the day."),
            ]
        },
    )

    text = render("issues", thread, until="2026-02-27")

    assert "- State: open" in text
    assert "Before." in text
    assert "On the day." not in text


def test_a_pull_request_shows_its_merge_branch_and_worded_reviews() -> None:
    thread = _issue(
        9,
        "2026-01-02T00:00:00Z",
        title="Add notes",
        mergedAt="2026-01-03T00:00:00Z",
        closedAt="2026-01-03T00:00:00Z",
        baseRefName="master",
        headRefName="notes",
        reviews={
            "nodes": [
                {
                    "author": {"login": "tim"},
                    "submittedAt": "2026-01-02T12:00:00Z",
                    "state": "CHANGES_REQUESTED",
                    "body": "Use the helper.",
                },
                {
                    "author": {"login": "tim"},
                    "submittedAt": "2026-01-02T13:00:00Z",
                    "state": "APPROVED",
                    "body": "",
                },
            ]
        },
    )

    text = render("pulls", thread)

    assert text.startswith("# Pull request #9: Add notes\n")
    assert "- State: merged on 2026-01-03" in text
    assert "- Branch: notes into master" in text
    assert "Review (changes requested) by tim on 2026-01-02" in text
    assert "Use the helper." in text
    assert "(approved)" not in text


def test_a_discussion_marks_its_answer_and_nests_replies() -> None:
    thread = _issue(
        3,
        "2026-01-01T00:00:00Z",
        category={"name": "Ideas"},
        answer={"id": "C2"},
        comments={
            "nodes": [
                _comment(
                    "bob",
                    "2026-01-02T00:00:00Z",
                    "Maybe.",
                    id="C1",
                    replies={
                        "nodes": [
                            _comment("ann", "2026-01-03T00:00:00Z", "No.")
                        ]
                    },
                ),
                _comment("tim", "2026-01-04T00:00:00Z", "Do this.", id="C2"),
            ]
        },
    )

    text = render("discussions", thread)

    assert "- Category: Ideas" in text
    assert "Reply by ann to bob on 2026-01-03" in text
    assert "Answer by tim on 2026-01-04" in text


def test_a_long_post_is_cut_with_a_note() -> None:
    thread = _issue(1, "2026-01-01T00:00:00Z", body="x" * 120)

    text = render("issues", thread, longest=100)

    assert "x" * 100 + "\n\n[cut: 20 more characters]" in text


def test_threads_follow_their_cursor_and_stop_at_until() -> None:
    post = _post(
        _page(_issue(1, "2026-01-01T00:00:00Z"), after="c1"),
        _page(
            _issue(2, "2026-02-01T00:00:00Z"),
            _issue(3, "2026-03-01T00:00:00Z"),
        ),
    )

    found = list(
        pages(_config(kinds=["issues"], until="2026-02-27"), post=post)
    )

    assert [p.path for p in found] == ["issues/issue-1.md", "issues/issue-2.md"]
    assert post.sent[1]["variables"]["after"] == "c1"
    assert post.sent[0]["headers"]["Authorization"] == f"Bearer {PLACEHOLDER}"


def test_a_long_comment_list_is_completed_through_its_cursor() -> None:
    first = _issue(
        1,
        "2026-01-01T00:00:00Z",
        comments={
            "pageInfo": {"hasNextPage": True, "endCursor": "k1"},
            "nodes": [_comment("bob", "2026-01-02T00:00:00Z", "One.")],
        },
    )
    more = {
        "data": {
            "node": {
                "comments": {
                    "pageInfo": {"hasNextPage": False},
                    "nodes": [_comment("cy", "2026-01-03T00:00:00Z", "Two.")],
                }
            }
        }
    }
    post = _post(_page(first), more)

    (page,) = pages(_config(kinds=["issues"]), post=post)

    assert "One." in page.body.decode()
    assert "Two." in page.body.decode()
    assert post.sent[1]["variables"] == {"id": "I1", "after": "k1"}


def test_the_version_is_the_rendered_text_not_the_last_activity() -> None:
    early = _issue(1, "2026-01-01T00:00:00Z", updatedAt="2026-01-02")
    late = _issue(
        1,
        "2026-01-01T00:00:00Z",
        comments={"nodes": [_comment("bob", "2026-05-01T00:00:00Z", "Later.")]},
    )
    cfg = _config(kinds=["issues"], until="2026-02-27")

    (before,) = pages(cfg, post=_post(_page(early)))
    (after,) = pages(cfg, post=_post(_page(late)))

    assert before.version == after.version


def test_refused_credentials_and_query_errors_are_domain_errors() -> None:
    with pytest.raises(SyncError, match="credentials"):
        list(pages(_config(), post=_post(status=401)))
    refused = {"errors": [{"message": "too many nodes"}]}
    with pytest.raises(SyncError, match="too many nodes"):
        list(pages(_config(), post=_post(refused)))


def test_an_unknown_kind_or_a_bad_repo_says_so() -> None:
    with pytest.raises(SyncError, match="thread kind"):
        list(pages(_config(kinds=["wikis"]), post=_post()))
    with pytest.raises(SyncError, match="owner"):
        list(pages(_config(repo="payments"), post=_post()))


def test_validation_rejects_a_token_that_cannot_read_the_repo() -> None:
    with pytest.raises(ValidationFailed, match="authentication"):
        validate_github_threads(_config(), post=_post(status=401))
    with pytest.raises(ValidationFailed, match="no repository"):
        validate_github_threads(
            _config(), post=_post({"data": {"repository": None}})
        )
    validate_github_threads(
        _config(), post=_post({"data": {"repository": {"id": "R"}}})
    )


def test_split_addresses_a_thread_by_repository_and_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hrono.ingest import github_threads as module

    post = _post(_page(_issue(5, "2026-01-01T00:00:00Z", body="Some prose.")))
    monkeypatch.setattr(module, "post_json", post)
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn:
        registry_store.insert(
            conn,
            "sources",
            "acme-threads",
            json.dumps(_config(kinds=["issues"])),
            None,
            "t",
        )
    context = JobContext(database, None, tmp_path / "cache")
    job = Job(
        id="j1",
        parent_id=None,
        tree=None,
        op="sync",
        scope={"name": "acme-threads"},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )

    sync(job, context)
    split_source(job, context)

    with database.connect() as conn:
        uris = [
            str(r["uri"])
            for r in conn.execute(
                "SELECT uri FROM sections WHERE source = 'acme-threads'"
            ).fetchall()
        ]
    database.close()

    assert uris
    assert all(
        u.startswith(
            "github-threads://github.com/acme/payments/issues/issue-5.md@"
        )
        for u in uris
    )
    assert github_threads_instance(_config(), tmp_path) == (
        "github.com/acme/payments"
    )


def test_a_source_with_a_cutoff_validates_and_stores_as_json() -> None:
    from pydantic import ValidationError

    from hrono.registry.collections.sources import Source

    config = Source.model_validate(_config(until="2026-02-27")).model_dump()

    assert json.loads(json.dumps(config))["until"] == "2026-02-27"
    with pytest.raises(ValidationError):
        Source.model_validate(_config(until="27 February"))
