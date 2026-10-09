"""Classify a source's file-level diff between two synced versions.

The entry point of incremental update: given the previously-ingested files and
the freshly-synced ones — each as a ``path -> content hash`` map — classify
every affected file as NEW / CHANGED / DELETED / MOVED so the incremental
pipeline (placement, propagate) touches only the delta. Classification is
by CONTENT HASH, like the embed/condense caches: a file whose bytes are
identical after a pull is not "changed"; a renamed file with identical bytes is
MOVED (same content, new path) so its vectors/condensations are reused.

``classify`` is pure; ``current_files`` (from the synced cache, honouring the
ingest filter) and ``stored_files`` (reconstructed from the last version's
stored sections) build the two maps. On first sync ``stored_files`` is empty, so
everything is NEW; a no-op re-sync classifies nothing.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from hrono.ingest.identity import content_hash
from hrono.ingest.readers import Reader
from hrono.ingest.store import get_content


@dataclass(frozen=True)
class Change:
    path: str
    status: str  # new | changed | deleted | moved
    old_path: str | None = None  # set only for moved (the prior path)


def classify(
    old: Mapping[str, str], new: Mapping[str, str]
) -> tuple[Change, ...]:
    """Classify new vs old file->hash maps into new/changed/deleted/moved."""
    changes: list[Change] = []
    added = {p: h for p, h in new.items() if p not in old}
    removed = {p: h for p, h in old.items() if p not in new}

    for path in old.keys() & new.keys():
        if old[path] != new[path]:
            changes.append(Change(path, "changed"))

    added_by_hash: dict[str, list[str]] = defaultdict(list)
    for path, digest in added.items():
        added_by_hash[digest].append(path)

    moved_targets: set[str] = set()
    for old_path in sorted(removed):
        candidates = [
            p
            for p in sorted(added_by_hash.get(removed[old_path], []))
            if p not in moved_targets
        ]
        if candidates:
            target = candidates[0]
            moved_targets.add(target)
            changes.append(Change(target, "moved", old_path=old_path))
        else:
            changes.append(Change(old_path, "deleted"))

    for path in added:
        if path not in moved_targets:
            changes.append(Change(path, "new"))

    return tuple(sorted(changes, key=lambda c: (c.status, c.path)))


def current_files(
    reader: Reader, config: dict[str, object], cache: Path
) -> dict[str, str]:
    """Return unit path -> content hash for what the source holds NOW.

    The units come from the source's own reader, so a diff over a
    non-filesystem source asks that source what it has rather than walking a
    directory that does not exist.
    """
    return {
        unit.path: content_hash(unit.body)
        for unit in reader.units(config, cache)
    }


def stored_files(conn: sqlite3.Connection, source: str) -> dict[str, str]:
    """Return path -> content hash for the source's last-ingested files.

    A file's bytes tile byte-for-byte across its stored sections, so the
    file hash is the hash of its sections concatenated in order — comparable to
    ``current_files`` (which hashes the raw file bytes).
    """
    bodies: dict[str, list[bytes]] = defaultdict(list)
    for row in conn.execute(
        "SELECT path, content_hash FROM sections WHERE source = ? "
        "ORDER BY path, ordinal, id",
        (source,),
    ).fetchall():
        bodies[row["path"]].append(
            get_content(conn, row["content_hash"]) or b""
        )
    return {
        path: content_hash(b"".join(parts)) for path, parts in bodies.items()
    }


def diff(
    conn: sqlite3.Connection,
    source: str,
    reader: Reader,
    config: dict[str, object],
    cache: Path,
) -> tuple[Change, ...]:
    """Classify the source's diff from its stored version to its units now."""
    return classify(
        stored_files(conn, source), current_files(reader, config, cache)
    )
