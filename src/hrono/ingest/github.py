"""The ``github-user`` source type: an owner's repos, discovered then cloned.

Discovery is how repos are FOUND, never their address
(``docs/api.md``): every repo a `github-user` source pulls in keeps the
identity it would have had as a git source of its own —
`git://github.com/<owner>/<repo>/<path>@<sha>` — so moving a repo in or out of
a discovery source never re-addresses its content.

Only the enumeration below is github's. Cloning, the name globs, the
repo -> commit map and reading the clones back are `discovery`'s, shared with
every other provider that answers "what repos exist here".
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from hrono.ingest import SyncError
from hrono.ingest.api import TIMEOUT, get_json
from hrono.ingest.discovery import clone_all, kept

API = "https://api.github.com"
HOST = "github.com"
PER_PAGE = 100


def repos(
    config: dict[str, object],
    *,
    fetch: object = None,
    timeout: float = TIMEOUT,
) -> tuple[tuple[str, str], ...]:
    """Return (repo name, clone url) for every repo the globs keep, sorted.

    Full re-discovery on every call (v1): the provider is the source of truth
    for what exists, and a stored list would go stale silently the first time
    someone archives a repo.
    """
    getter = fetch if fetch is not None else get_json
    owner = str(config["owner"])
    headers = _headers(config.get("auth"))
    found: list[tuple[str, str]] = []
    page = 1
    while True:
        url = f"{API}/users/{owner}/repos?per_page={PER_PAGE}&page={page}"
        status, body = getter(url, headers, timeout)  # type: ignore[operator]
        _raise_for(status, body, owner)
        entries: Sequence[object] = body  # type: ignore[assignment]
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", ""))
            clone = str(entry.get("clone_url", ""))
            if name and clone:
                found.append((name, clone))
        if len(entries) < PER_PAGE:
            break
        page += 1
    return kept(found, config)


def _raise_for(status: int, body: object, owner: str) -> None:
    if status == 404:
        raise SyncError(f"no such github owner: {owner}")
    if status in (401, 403):
        raise SyncError("github refused the credentials")
    if status != 200 or not isinstance(body, list):
        raise SyncError(f"github returned {status} for owner: {owner}")


def github_sync(config: dict[str, object], cache: Path, timeout: float) -> str:
    """Clone or pull every repo this owner exposes; return the version."""
    return clone_all(config, cache, timeout, lambda c: repos(c))


def github_instance(config: dict[str, object], cache: Path) -> str:
    """The owner's root: a repo's name is the first segment of a unit path."""
    return f"{HOST}/{config['owner']}"


def validate_github_user(
    config: dict[str, object],
    context: object = None,
    *,
    fetch: object = None,
    timeout: float = TIMEOUT,
) -> None:
    """Reject the write unless the owner resolves and the token works."""
    from hrono.registry.descriptor import ValidationFailed

    getter = fetch if fetch is not None else get_json
    owner = str(config["owner"])
    status, _body = getter(  # type: ignore[operator]
        f"{API}/users/{owner}", _headers(config.get("auth")), timeout
    )
    if status == 200:
        return
    if status == 404:
        raise ValidationFailed(f"no such github owner: {owner}")
    if status in (401, 403):
        raise ValidationFailed("authentication failed")
    raise ValidationFailed(f"github returned {status}")


def _headers(auth: object) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if isinstance(auth, dict) and auth.get("method") == "token":
        headers["Authorization"] = f"Bearer {auth['token']}"
    return headers


__all__ = [
    "github_instance",
    "github_sync",
    "repos",
    "validate_github_user",
]
