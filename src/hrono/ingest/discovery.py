"""What every DISCOVERY source type shares: clone the repos, read them back.

A discovery source (#147 github-user, #148 bitbucket-workspace) differs from
its siblings in exactly one place — how the provider is asked what repos
exist. Everything after that answer is identical and lives here: the name
globs, cloning each repo through the git syncer, recording the repo -> commit
map, and reading the clones back as units that carry their own repo's commit.

The heads map is read from the cache, never re-derived with ``git rev-parse``:
a reader must describe the bytes the SYNC left there, and a repo pulled by
something else in between would otherwise be addressed at a commit whose
content was never ingested.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

from hrono.ingest import SyncError, Unit
from hrono.ingest.git_reader import git_units
from hrono.ingest.git_syncer import git_sync

Enumerate = Callable[[dict[str, object]], Sequence[tuple[str, str]]]
_HEADS = ".hrono-heads.json"


def clone_all(
    config: dict[str, object],
    cache: Path,
    timeout: float,
    enumerate_repos: Enumerate,
) -> str:
    """Clone or pull every discovered repo; return a digest over their heads."""
    heads: dict[str, str] = {}
    for name, clone_url in enumerate_repos(config):
        heads[name] = git_sync(
            {
                "name": f"{config['name']}/{name}",
                "url": clone_url,
                "auth": config.get("auth") or {"method": "none"},
            },
            cache / name,
            timeout,
        )
    cache.mkdir(parents=True, exist_ok=True)
    (cache / _HEADS).write_text(json.dumps(heads, sort_keys=True))
    return hashlib.sha256(
        json.dumps(heads, sort_keys=True).encode()
    ).hexdigest()


def units(config: dict[str, object], cache: Path) -> Iterator[Unit]:
    """Every ingestable file of every clone, path-prefixed by its repo."""
    for name, head in sorted(heads(cache).items()):
        for unit in git_units(config, cache / name):
            yield Unit(f"{name}/{unit.path}", unit.body, version=head)


def unit(config: dict[str, object], cache: Path, path: str) -> Unit:
    """One file, addressed ``<repo>/<path within that repo>``."""
    name, _, inner = path.partition("/")
    head = heads(cache).get(name)
    if head is None:
        raise SyncError(f"no such discovered repo: {name}")
    return Unit(path, (cache / name / inner).read_bytes(), version=head)


def heads(cache: Path) -> dict[str, str]:
    """The repo -> commit map the last sync wrote."""
    path = cache / _HEADS
    if not path.exists():
        raise SyncError("this source has not been synced yet")
    loaded = json.loads(path.read_text())
    return {str(k): str(v) for k, v in loaded.items()}


def kept(
    found: Sequence[tuple[str, str]], config: dict[str, object]
) -> tuple[tuple[str, str], ...]:
    """Apply the source's repo-NAME globs; include narrows, exclude removes."""
    include = _globs(config.get("include"))
    exclude = _globs(config.get("exclude"))
    keep = []
    for name, url in found:
        if include and not any(fnmatch.fnmatch(name, g) for g in include):
            continue
        if any(fnmatch.fnmatch(name, g) for g in exclude):
            continue
        keep.append((name, url))
    return tuple(sorted(keep))


def _globs(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)
