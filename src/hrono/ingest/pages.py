"""What every API-ONLY source type shares: pull pages, then read them back.

Confluence and Notion have nothing to clone. Their syncer PULLS
each page and materializes it in the source's cache; their reader reads those
files back. That is not a workaround for the reader contract — the cache is
"where this source's current content lives", and a pulled page is exactly
that. Materializing also means the diff compares bytes hrono actually holds
rather than re-asking the provider twice per update.

A page carries its OWN version (``Unit.version``): a space of four
hundred pages where one was edited must re-ingest one page, not four hundred.
The source's own version is a digest over the whole page -> version map, so it
moves when anything in scope moves.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from hrono.ingest import SyncError, Unit

_VERSIONS = ".hrono-pages.json"


@dataclass(frozen=True)
class Page:
    """One pulled page: where it lands, what it says, and which version."""

    path: str
    body: bytes
    version: str


def materialize(cache: Path, pages: Sequence[Page]) -> str:
    """Write every page under ``cache``; return the source's own version.

    The cache is REPLACED, not merged: a page that left the scope must leave
    the cache too, or the next diff reports it as present for ever.
    """
    _clear(cache)
    versions: dict[str, str] = {}
    for page in pages:
        target = cache / page.path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(page.body)
        versions[page.path] = page.version
    cache.mkdir(parents=True, exist_ok=True)
    (cache / _VERSIONS).write_text(json.dumps(versions, sort_keys=True))
    return hashlib.sha256(
        json.dumps(versions, sort_keys=True).encode()
    ).hexdigest()


def units(config: dict[str, object], cache: Path) -> Iterator[Unit]:
    """Every materialized page, each carrying its own version.

    An EMPTY page is skipped, matching ``filter.survey``'s zero-byte rule for
    git files: an empty unit splits to no sections, so ``stored_files`` never
    records it and every later diff reports it "new" again — a batch
    allocated, the pool aged and condense run on every sync of an unchanged
    corpus, for a page with nothing on it.
    """
    for path, version in sorted(versions(cache).items()):
        body = (cache / path).read_bytes()
        if not body:
            continue
        yield Unit(path, body, version=version)


def unit(config: dict[str, object], cache: Path, path: str) -> Unit:
    """One materialized page, by the path the sync gave it."""
    version = versions(cache).get(path)
    if version is None:
        raise SyncError(f"no such page in this source: {path}")
    return Unit(path, (cache / path).read_bytes(), version=version)


def versions(cache: Path) -> dict[str, str]:
    """The page -> version map the last sync wrote."""
    path = cache / _VERSIONS
    if not path.exists():
        raise SyncError("this source has not been synced yet")
    loaded = json.loads(path.read_text())
    return {str(k): str(v) for k, v in loaded.items()}


def _clear(cache: Path) -> None:
    import shutil

    if cache.exists():
        shutil.rmtree(cache)
