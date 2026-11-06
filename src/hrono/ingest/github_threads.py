"""The ``github-threads`` source type: a repository's conversations.

Issues, pull requests and discussions hold what a repository's code does not:
why a change was made, what was decided and rejected, how a feature is meant
to be used. This type pulls each thread through GitHub's GraphQL API and
renders it as one markdown page — title, state, labels, the opening post and
every comment and review in order — and nothing of a pull request's diff,
which the repository's own git source already holds.

Three decisions worth stating, because they are not free choices:

- ``until`` cuts the repository's conversation at a date: a thread opened on
  or after it is left out, a comment or review made after it is dropped, and
  a thread closed or merged after it reads as open. It is what keeps a source
  pinned at a past commit from reading the future. GitHub does not date the
  edits of an opening post, so a post edited after ``until`` shows its
  current text.
- a page's version is a digest of its rendered text, not the thread's
  ``updatedAt``: with ``until`` set, a thread that moves on after the cutoff
  renders the same page, and must not re-ingest.
- a post longer than ``longest_post`` characters (8,000 by default) is cut
  with a note saying so. The long ones are pasted logs and `git status` file
  lists of squash merges, not conversation, and would otherwise be a third
  of a repository's threads by size.
- the address is ``github-threads://<host>/<owner>/<repo>/<kind>/<kind>-<n>.md
  @<digest>``: the instance is the repository, as a git source of the same
  repository has it, so a thread and the code it discusses share a prefix.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Sequence
from pathlib import Path

from hrono.ingest import SyncError
from hrono.ingest.api import TIMEOUT, post_json
from hrono.ingest.pages import Page, materialize

API = "https://api.github.com/graphql"
HOST = "github.com"
# GitHub refuses a query that could return over 500,000 nodes: threads x
# comments x replies must stay under it.
PAGE_SIZE = 25
COMMENTS = 100
REPLIES = 50
LONGEST_POST = 8000
KINDS = ("issues", "pulls", "discussions")

_AUTHOR = "author { login }"
_COMMENT = f"{_AUTHOR} createdAt body"
_THREAD = f"number title url createdAt closedAt {_AUTHOR} body"
_LABELS = "labels(first: 20) { nodes { name } }"

# One query per kind. Each asks for a page of threads, oldest first, with the
# first page of their comments; a thread with more is completed by
# ``_COMMENTS_QUERY`` below.
_QUERIES = {
    "issues": f"""
query($owner: String!, $name: String!, $after: String) {{
  repository(owner: $owner, name: $name) {{
    threads: issues(first: {PAGE_SIZE}, after: $after,
                    orderBy: {{field: CREATED_AT, direction: ASC}}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        id {_THREAD} state stateReason {_LABELS}
        comments(first: {COMMENTS}) {{
          pageInfo {{ hasNextPage endCursor }} nodes {{ {_COMMENT} }}
        }}
      }}
    }}
  }}
}}""",
    "pulls": f"""
query($owner: String!, $name: String!, $after: String) {{
  repository(owner: $owner, name: $name) {{
    threads: pullRequests(first: {PAGE_SIZE}, after: $after,
                          orderBy: {{field: CREATED_AT, direction: ASC}}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        id {_THREAD} state mergedAt baseRefName headRefName {_LABELS}
        comments(first: {COMMENTS}) {{
          pageInfo {{ hasNextPage endCursor }} nodes {{ {_COMMENT} }}
        }}
        reviews(first: {COMMENTS}) {{
          nodes {{ {_AUTHOR} submittedAt state body }}
        }}
      }}
    }}
  }}
}}""",
    "discussions": f"""
query($owner: String!, $name: String!, $after: String) {{
  repository(owner: $owner, name: $name) {{
    threads: discussions(first: {PAGE_SIZE}, after: $after,
                         orderBy: {{field: CREATED_AT, direction: ASC}}) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{
        id {_THREAD} {_LABELS} category {{ name }} answer {{ id }}
        comments(first: {COMMENTS}) {{
          pageInfo {{ hasNextPage endCursor }}
          nodes {{
            id {_COMMENT}
            replies(first: {REPLIES}) {{ nodes {{ {_COMMENT} }} }}
          }}
        }}
      }}
    }}
  }}
}}""",
}

_COMMENTS_QUERY = f"""
query($id: ID!, $after: String) {{
  node(id: $id) {{
    ... on Issue {{ comments(first: {COMMENTS}, after: $after) {{
      pageInfo {{ hasNextPage endCursor }} nodes {{ {_COMMENT} }} }} }}
    ... on PullRequest {{ comments(first: {COMMENTS}, after: $after) {{
      pageInfo {{ hasNextPage endCursor }} nodes {{ {_COMMENT} }} }} }}
    ... on Discussion {{ comments(first: {COMMENTS}, after: $after) {{
      pageInfo {{ hasNextPage endCursor }}
      nodes {{ id {_COMMENT}
               replies(first: {REPLIES}) {{ nodes {{ {_COMMENT} }} }} }} }} }}
  }}
}}"""

_NAMES = {
    "issues": "Issue",
    "pulls": "Pull request",
    "discussions": "Discussion",
}
_FILES = {"issues": "issue", "pulls": "pull", "discussions": "discussion"}


def github_threads_sync(
    config: dict[str, object],
    cache: Path,
    timeout: float,
    *,
    post: object = None,
) -> str:
    """Render every thread in scope into the cache; return its version."""
    return materialize(cache, tuple(pages(config, post=post, timeout=timeout)))


def pages(
    config: dict[str, object],
    *,
    post: object = None,
    timeout: float = TIMEOUT,
) -> Iterator[Page]:
    """Every thread of every kind in scope, rendered as of ``until``."""
    poster = post if post is not None else post_json
    owner, name = _repository(config)
    headers = _headers(config.get("auth"))
    until = _until(config)
    for kind in _kinds(config):
        for thread in _threads(poster, headers, kind, owner, name, timeout):
            if until and str(thread.get("createdAt") or "") >= until:
                break  # oldest first: everything after is past the cutoff
            thread["comments"] = _all_comments(poster, headers, thread, timeout)
            body = render(kind, thread, until, _longest(config))
            yield Page(
                path=f"{kind}/{_FILES[kind]}-{thread['number']}.md",
                body=body.encode(),
                version=hashlib.sha256(body.encode()).hexdigest()[:16],
            )


def render(
    kind: str,
    thread: dict[str, object],
    until: str = "",
    longest: int = LONGEST_POST,
) -> str:
    """One thread as markdown: heading, facts, the opening post, the replies.

    Everything dated on or after ``until`` is left out; a state reached after
    it reads as open. Each post is cut at ``longest`` characters.
    """
    lines = [f"# {_NAMES[kind]} #{thread['number']}: {thread.get('title', '')}"]
    facts = [
        f"State: {_state(kind, thread, until)}",
        f"Opened by {_login(thread)} on {_day(thread.get('createdAt'))}",
    ]
    labels = _names(thread.get("labels"))
    if labels:
        facts.append("Labels: " + ", ".join(labels))
    category = thread.get("category")
    if isinstance(category, dict) and category.get("name"):
        facts.append(f"Category: {category['name']}")
    if kind == "pulls" and thread.get("baseRefName"):
        facts.append(
            f"Branch: {thread.get('headRefName')} into {thread['baseRefName']}"
        )
    lines += ["", "\n".join(f"- {fact}" for fact in facts)]
    body = _cut(str(thread.get("body") or "").strip(), longest)
    lines += ["", body or "(no description)"]
    for heading, entry in _replies(kind, thread, until):
        text = _cut(str(entry.get("body") or "").strip(), longest)
        lines += ["", f"## {heading}", "", text]
    return "\n".join(lines).rstrip() + "\n"


def _replies(
    kind: str, thread: dict[str, object], until: str
) -> Iterator[tuple[str, dict[str, object]]]:
    """Comments, discussion replies and review bodies, oldest first."""
    entries: list[tuple[str, str, dict[str, object]]] = []
    answer = thread.get("answer")
    answer_id = answer.get("id") if isinstance(answer, dict) else None
    for comment in _list(_nodes(thread.get("comments"))):
        when = str(comment.get("createdAt") or "")
        what = (
            "Answer"
            if answer_id and comment.get("id") == answer_id
            else "Comment"
        )
        entries.append((when, f"{what} by {_login(comment)}", comment))
        for reply in _list(_nodes(comment.get("replies"))):
            entries.append(
                (
                    str(reply.get("createdAt") or ""),
                    f"Reply by {_login(reply)} to {_login(comment)}",
                    reply,
                )
            )
    for review in _list(_nodes(thread.get("reviews"))):
        if not str(review.get("body") or "").strip():
            continue  # an approval with no words says nothing to read
        state = str(review.get("state") or "").lower().replace("_", " ")
        entries.append(
            (
                str(review.get("submittedAt") or ""),
                f"Review ({state}) by {_login(review)}",
                review,
            )
        )
    for when, heading, entry in sorted(entries, key=lambda e: e[0]):
        if until and when >= until:
            continue
        yield f"{heading} on {_day(when)}", entry


def _cut(text: str, longest: int) -> str:
    if len(text) <= longest:
        return text
    return f"{text[:longest]}\n\n[cut: {len(text) - longest} more characters]"


def _state(kind: str, thread: dict[str, object], until: str) -> str:
    """Open, closed or merged as of ``until`` (now when it is unset)."""
    merged = str(thread.get("mergedAt") or "")
    closed = str(thread.get("closedAt") or "")
    if merged and (not until or merged < until):
        return f"merged on {_day(merged)}"
    if closed and (not until or closed < until):
        reason = str(thread.get("stateReason") or "").lower().replace("_", " ")
        return f"closed on {_day(closed)}" + (f" ({reason})" if reason else "")
    return "open"


def _threads(
    poster: object,
    headers: dict[str, str],
    kind: str,
    owner: str,
    name: str,
    timeout: float,
) -> Iterator[dict[str, object]]:
    after: str | None = None
    while True:
        data = _query(
            poster,
            headers,
            _QUERIES[kind],
            {"owner": owner, "name": name, "after": after},
            timeout,
        )
        repository = data.get("repository")
        if not isinstance(repository, dict):
            raise SyncError(f"github found no repository {owner}/{name}")
        found = repository.get("threads")
        if not isinstance(found, dict):
            raise SyncError("github returned an unexpected body")
        yield from _list(found.get("nodes"))
        after = _next(found)
        if after is None:
            return


def _all_comments(
    poster: object,
    headers: dict[str, str],
    thread: dict[str, object],
    timeout: float,
) -> list[dict[str, object]]:
    """The thread's comments, following their cursor past the first page."""
    page = thread.get("comments")
    comments = list(_list(_nodes(page)))
    after = _next(page)
    while after is not None:
        data = _query(
            poster,
            headers,
            _COMMENTS_QUERY,
            {"id": thread.get("id"), "after": after},
            timeout,
        )
        node = data.get("node")
        page = node.get("comments") if isinstance(node, dict) else None
        comments += _list(_nodes(page))
        after = _next(page)
    return comments


def _query(
    poster: object,
    headers: dict[str, str],
    query: str,
    variables: dict[str, object],
    timeout: float,
) -> dict[str, object]:
    status, body = poster(  # type: ignore[operator]
        API, headers, {"query": query, "variables": variables}, timeout
    )
    _raise_for(status)
    if not isinstance(body, dict):
        raise SyncError("github returned an unexpected body")
    errors = body.get("errors")
    if errors:
        first = errors[0] if isinstance(errors, list) and errors else errors
        message = first.get("message") if isinstance(first, dict) else first
        raise SyncError(f"github refused the query: {message}")
    data = body.get("data")
    if not isinstance(data, dict):
        raise SyncError("github returned an unexpected body")
    return data


def _next(page: object) -> str | None:
    info = page.get("pageInfo") if isinstance(page, dict) else None
    if isinstance(info, dict) and info.get("hasNextPage"):
        cursor = info.get("endCursor")
        return str(cursor) if cursor else None
    return None


def _nodes(page: object) -> object:
    return page.get("nodes") if isinstance(page, dict) else page


def _list(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [entry for entry in value if isinstance(entry, dict)]


def _names(page: object) -> list[str]:
    return [str(n.get("name")) for n in _list(_nodes(page)) if n.get("name")]


def _login(entry: dict[str, object]) -> str:
    author = entry.get("author")
    login = author.get("login") if isinstance(author, dict) else None
    return str(login) if login else "a deleted user"


def _day(stamp: object) -> str:
    return str(stamp or "")[:10]


def _repository(config: dict[str, object]) -> tuple[str, str]:
    owner, _, name = str(config.get("repo") or "").partition("/")
    if not owner or not name or "/" in name:
        raise SyncError("repo must be <owner>/<name>")
    return owner, name


def _kinds(config: dict[str, object]) -> Sequence[str]:
    chosen = config.get("kinds")
    if not isinstance(chosen, list) or not chosen:
        return KINDS
    unknown = [k for k in chosen if k not in KINDS]
    if unknown:
        raise SyncError(f"unsupported thread kind: {unknown[0]}")
    return tuple(k for k in KINDS if k in chosen)


def _longest(config: dict[str, object]) -> int:
    value = config.get("longest_post")
    return value if isinstance(value, int) and value > 0 else LONGEST_POST


def _until(config: dict[str, object]) -> str:
    """The cutoff as an ISO prefix that compares with GitHub's timestamps."""
    return str(config.get("until") or "")


def github_threads_instance(config: dict[str, object], cache: Path) -> str:
    """The repository, as a git source of the same repository addresses it."""
    owner, name = _repository(config)
    return f"{HOST}/{owner}/{name}"


def validate_github_threads(
    config: dict[str, object],
    context: object = None,
    *,
    post: object = None,
    timeout: float = TIMEOUT,
) -> None:
    """Reject the write unless the token reads the repository."""
    from hrono.registry.descriptor import ValidationFailed

    poster = post if post is not None else post_json
    try:
        owner, name = _repository(config)
    except SyncError as exc:
        raise ValidationFailed(str(exc)) from exc
    status, body = poster(  # type: ignore[operator]
        API,
        _headers(config.get("auth")),
        {
            "query": "query($o: String!, $n: String!) "
            "{ repository(owner: $o, name: $n) { id } }",
            "variables": {"o": owner, "n": name},
        },
        timeout,
    )
    if status in (401, 403):
        raise ValidationFailed("authentication failed")
    if status != 200:
        raise ValidationFailed(f"github returned {status}")
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict) or not data.get("repository"):
        raise ValidationFailed(f"github found no repository {owner}/{name}")


def _raise_for(status: int) -> None:
    if status in (401, 403):
        raise SyncError("github refused the credentials")
    if status != 200:
        raise SyncError(f"github returned {status}")


def _headers(auth: object) -> dict[str, str]:
    """GitHub's GraphQL API answers only an authenticated caller."""
    headers = {"Accept": "application/json"}
    if isinstance(auth, dict) and auth.get("method") == "token":
        headers["Authorization"] = f"Bearer {auth['token']}"
    return headers


__all__ = [
    "github_threads_instance",
    "github_threads_sync",
    "pages",
    "render",
    "validate_github_threads",
]
