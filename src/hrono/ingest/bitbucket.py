"""The ``bitbucket-workspace`` source type: a workspace's repos (T41.1).

Everything #147 settled for `github-user` holds here — one source row, each
repo keeping its own commit, every unit addressed `git://` because discovery
is not an address — so all that is new is the enumeration, and it differs from
github's in exactly two ways worth naming:

- bitbucket pages by a ``next`` URL carried IN the body, not by a page counter,
  so the loop follows what the server gives it rather than guessing the next
  page's number;
- a repo's clone url is one of several links; the ``https`` one is the one git
  can use with a token, as ``x-token-auth`` (implementation-notes.md).
"""

from __future__ import annotations

from collections.abc import Sequence

from hrono.ingest import SyncError
from hrono.ingest.api import TIMEOUT, get_json
from hrono.ingest.discovery import clone_all, kept

API = "https://api.bitbucket.org/2.0"
HOST = "bitbucket.org"
PAGE_LEN = 100


def repos(
    config: dict[str, object],
    *,
    fetch: object = None,
    timeout: float = TIMEOUT,
) -> tuple[tuple[str, str], ...]:
    """Return (repo name, https clone url) for every repo the globs keep."""
    getter = fetch if fetch is not None else get_json
    workspace = str(config["owner"])
    headers = _headers(config.get("auth"))
    url: str | None = f"{API}/repositories/{workspace}?pagelen={PAGE_LEN}"
    found: list[tuple[str, str]] = []
    while url:
        status, body = getter(url, headers, timeout)  # type: ignore[operator]
        page = _page(status, body, workspace)
        for entry in page.get("values", []):
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("slug") or entry.get("name") or "")
            clone = _clone_url(entry)
            if name and clone:
                found.append((name, clone))
        nxt = page.get("next")
        url = str(nxt) if isinstance(nxt, str) and nxt else None
    return kept(found, config)


def _page(status: int, body: object, workspace: str) -> dict[str, object]:
    if status == 404:
        raise SyncError(f"no such bitbucket workspace: {workspace}")
    if status in (401, 403):
        raise SyncError("bitbucket refused the credentials")
    if status != 200 or not isinstance(body, dict):
        raise SyncError(
            f"bitbucket returned {status} for workspace: {workspace}"
        )
    return body


def _clone_url(entry: dict[str, object]) -> str:
    """The https clone link; the ssh one needs a key git may not have."""
    links = entry.get("links")
    if not isinstance(links, dict):
        return ""
    clones: Sequence[object] = links.get("clone") or ()  # type: ignore[assignment]
    for link in clones:
        if isinstance(link, dict) and link.get("name") == "https":
            return str(link.get("href", ""))
    return ""


def bitbucket_sync(
    config: dict[str, object], cache: object, timeout: float
) -> str:
    """Clone or pull every repo in the workspace; return the source version."""
    return clone_all(config, cache, timeout, lambda c: repos(c))  # type: ignore[arg-type]


def bitbucket_instance(config: dict[str, object]) -> str:
    """The workspace root: a repo's slug is the first segment of a unit path."""
    return f"{HOST}/{config['owner']}"


def validate_bitbucket_workspace(
    config: dict[str, object],
    context: object = None,
    *,
    fetch: object = None,
    timeout: float = TIMEOUT,
) -> None:
    """Reject the write unless the workspace resolves and the token works."""
    from hrono.registry.descriptor import ValidationFailed

    getter = fetch if fetch is not None else get_json
    workspace = str(config["owner"])
    status, _body = getter(  # type: ignore[operator]
        f"{API}/workspaces/{workspace}",
        _headers(config.get("auth")),
        timeout,
    )
    if status == 200:
        return
    if status == 404:
        raise ValidationFailed(f"no such bitbucket workspace: {workspace}")
    if status in (401, 403):
        raise ValidationFailed("authentication failed")
    raise ValidationFailed(f"bitbucket returned {status}")


def _headers(auth: object) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    if isinstance(auth, dict) and auth.get("method") == "token":
        headers["Authorization"] = f"Bearer {auth['token']}"
    return headers


__all__ = [
    "bitbucket_instance",
    "bitbucket_sync",
    "repos",
    "validate_bitbucket_workspace",
]
