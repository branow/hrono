"""The ``github-user`` source type: an owner's repos, discovered then cloned.

Discovery is how repos are FOUND, never their address (implementation-notes):
every repo a `github-user` source pulls in keeps the identity it would have had
as a git source of its own — `git://github.com/<owner>/<repo>/<path>@<sha>` —
so moving a repo in or out of a discovery source never re-addresses its
content.

One source row holds them all. Its cache is a directory of clones, one per
repo; its version is a digest over the sorted repo -> commit map, which moves
when any repo moves; and each unit carries its OWN repo's commit, so a repo
that did not change is not re-ingested because a sibling did.

Everything below the discovery step is the git type's: `git_sync` clones and
pulls each repo, `git_units` applies the same filter rules to each working
tree. What is new here is only the enumeration and the name globs.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import httpx

from hrono.ingest import SyncError, Unit
from hrono.ingest.git_reader import git_units
from hrono.ingest.git_syncer import git_sync

API = "https://api.github.com"
HOST = "github.com"
PER_PAGE = 100
_TIMEOUT = 30.0

Fetch = Callable[[str, dict[str, str], float], tuple[int, object]]


def repos(
    config: dict[str, object],
    *,
    fetch: Fetch | None = None,
    timeout: float = _TIMEOUT,
) -> tuple[tuple[str, str], ...]:
    """Return (repo name, clone url) for every repo the globs keep, sorted.

    Full re-discovery on every call (v1): the provider is the source of truth
    for what exists, and a stored list would go stale silently the first time
    someone archives a repo.
    """
    getter = fetch if fetch is not None else _get
    owner = str(config["owner"])
    headers = _headers(config.get("auth"))
    found: list[tuple[str, str]] = []
    page = 1
    while True:
        url = f"{API}/users/{owner}/repos?per_page={PER_PAGE}&page={page}"
        status, body = getter(url, headers, timeout)
        if status == 404:
            raise SyncError(f"no such github owner: {owner}")
        if status == 401 or status == 403:
            raise SyncError("github refused the credentials")
        if status != 200 or not isinstance(body, list):
            raise SyncError(f"github returned {status} for owner: {owner}")
        for entry in body:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", ""))
            clone = str(entry.get("clone_url", ""))
            if name and clone:
                found.append((name, clone))
        if len(body) < PER_PAGE:
            break
        page += 1
    return tuple(sorted(_kept(found, config)))


def github_sync(config: dict[str, object], cache: Path, timeout: float) -> str:
    """Clone or pull every discovered repo; return a digest over their heads."""
    heads: dict[str, str] = {}
    for name, clone_url in repos(config):
        repo_config = {
            "name": f"{config['name']}/{name}",
            "url": clone_url,
            "auth": config.get("auth") or {"method": "none"},
        }
        heads[name] = git_sync(repo_config, cache / name, timeout)
    _write_heads(cache, heads)
    return _digest(heads)


def github_units(config: dict[str, object], cache: Path) -> Iterator[Unit]:
    """Every ingestable file of every clone, path-prefixed by its repo."""
    for name, head in sorted(_read_heads(cache).items()):
        for unit in git_units(config, cache / name):
            yield Unit(f"{name}/{unit.path}", unit.body, version=head)


def github_unit(config: dict[str, object], cache: Path, path: str) -> Unit:
    """One file, addressed `<repo>/<path within that repo>`."""
    name, _, inner = path.partition("/")
    head = _read_heads(cache).get(name)
    if head is None:
        raise SyncError(f"no such discovered repo: {name}")
    return Unit(path, (cache / name / inner).read_bytes(), version=head)


def github_instance(config: dict[str, object]) -> str:
    """The owner's root: a repo's name is the first segment of a unit path."""
    return f"{HOST}/{config['owner']}"


def validate_github_user(
    config: dict[str, object],
    context: object = None,
    *,
    fetch: Fetch | None = None,
    timeout: float = _TIMEOUT,
) -> None:
    """Reject the write unless the owner resolves and the token works."""
    from hrono.registry.descriptor import ValidationFailed

    getter = fetch if fetch is not None else _get
    owner = str(config["owner"])
    status, _body = getter(
        f"{API}/users/{owner}", _headers(config.get("auth")), timeout
    )
    if status == 200:
        return
    if status == 404:
        raise ValidationFailed(f"no such github owner: {owner}")
    if status in (401, 403):
        raise ValidationFailed("authentication failed")
    raise ValidationFailed(f"github returned {status}")


def _kept(
    found: Sequence[tuple[str, str]], config: dict[str, object]
) -> list[tuple[str, str]]:
    include = _globs(config.get("include"))
    exclude = _globs(config.get("exclude"))
    kept = []
    for name, url in found:
        if include and not any(fnmatch.fnmatch(name, g) for g in include):
            continue
        if any(fnmatch.fnmatch(name, g) for g in exclude):
            continue
        kept.append((name, url))
    return kept


def _globs(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


def _headers(auth: object) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if isinstance(auth, dict) and auth.get("method") == "token":
        headers["Authorization"] = f"Bearer {auth['token']}"
    return headers


def _get(
    url: str, headers: dict[str, str], timeout: float
) -> tuple[int, object]:
    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        raise SyncError(f"cannot reach github: {type(exc).__name__}") from exc
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None


def _heads_file(cache: Path) -> Path:
    return cache / ".hrono-heads.json"


def _write_heads(cache: Path, heads: dict[str, str]) -> None:
    cache.mkdir(parents=True, exist_ok=True)
    _heads_file(cache).write_text(json.dumps(heads, sort_keys=True))


def _read_heads(cache: Path) -> dict[str, str]:
    """The repo -> commit map the last sync wrote.

    Read from the cache rather than re-derived with `git rev-parse` per repo:
    the reader must describe the bytes the SYNC left there, and a repo pulled
    by something else between the two would otherwise be addressed at a commit
    whose content was never ingested.
    """
    path = _heads_file(cache)
    if not path.exists():
        raise SyncError("this source has not been synced yet")
    loaded = json.loads(path.read_text())
    return {str(k): str(v) for k, v in loaded.items()}


def _digest(heads: dict[str, str]) -> str:
    body = json.dumps(heads, sort_keys=True).encode()
    return hashlib.sha256(body).hexdigest()


__all__ = [
    "github_instance",
    "github_sync",
    "github_unit",
    "github_units",
    "repos",
    "validate_github_user",
]
