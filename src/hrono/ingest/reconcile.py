"""Apply a file-level diff to the section store, section by section (#085, T34).

The bridge between #083's file diff and the #085 placement rule: it mutates only
the sections of the changed files (untouched files keep their sections and their
cluster membership untouched) and returns the section-level deltas the placement
rule consumes — each carrying the PRIOR cluster of the chunk it replaces so the
sticky re-check has a target. Matching new sections to old is by CONTENT HASH
first (an unchanged section inside an edited file maps to itself and stays put),
then by ordinal for the genuinely edited slots; an old section left unmatched is
a deletion.

A changed/deleted/moved file's old sections are dropped (their memberships
cascade away); the placement rule re-attaches the survivors. Bodies are stored
by content hash, so a moved file's content is reused and never re-embedded.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from pathlib import Path

from hrono.cluster import store as cluster_store
from hrono.cluster.blend import register_path_bodies
from hrono.cluster.placement import SectionDelta
from hrono.ingest.diff import Change
from hrono.ingest.split_op import store_file
from hrono.recall import fts

_OldSection = tuple[int, int, str, int | None]  # id, ordinal, hash, node_id


def reconcile(
    conn: sqlite3.Connection,
    *,
    tree: str,
    source: str,
    source_type: str,
    instance: str,
    version: str,
    cache: Path,
    changes: Sequence[Change],
) -> tuple[SectionDelta, ...]:
    """Mutate the store for a file diff; return the section-level deltas."""
    register_path_bodies(
        conn, [c.path for c in changes if c.status != "deleted"]
    )
    deltas: list[SectionDelta] = []
    for change in changes:
        deltas.extend(
            _apply(
                conn,
                tree,
                source,
                source_type,
                instance,
                version,
                cache,
                change,
            )
        )
    return tuple(deltas)


def _apply(
    conn: sqlite3.Connection,
    tree: str,
    source: str,
    source_type: str,
    instance: str,
    version: str,
    cache: Path,
    change: Change,
) -> list[SectionDelta]:
    if change.status == "new":
        stored = store_file(
            conn, cache, change.path, source, source_type, instance, version
        )
        return [
            SectionDelta("new", h, change.path, section_id=sid)
            for sid, _, h in stored
        ]
    if change.status == "deleted":
        old = _old_sections(conn, tree, source, change.path)
        _drop_path(conn, source, change.path)
        return [
            SectionDelta("deleted", h, change.path, prior_node_id=node)
            for _, _, h, node in old
        ]
    old_path = change.old_path if change.status == "moved" else change.path
    kind = "moved" if change.status == "moved" else "changed"
    old = _old_sections(conn, tree, source, old_path)
    _drop_path(conn, source, old_path)
    stored = store_file(
        conn, cache, change.path, source, source_type, instance, version
    )
    return _match(kind, change.path, old, stored)


def _match(
    kind: str,
    path: str,
    old: Sequence[_OldSection],
    stored: Sequence[tuple[int, int, str]],
) -> list[SectionDelta]:
    consumed = [False] * len(old)
    deltas: list[SectionDelta] = []
    for section_id, ordinal, content_hash in stored:
        prior = _consume(old, consumed, lambda e, h=content_hash: e[2] == h)
        if prior is None:
            prior = _consume(old, consumed, lambda e, o=ordinal: e[1] == o)
        deltas.append(
            SectionDelta(
                kind,
                content_hash,
                path,
                section_id=section_id,
                prior_node_id=prior,
            )
        )
    for index, (_, _, content_hash, node) in enumerate(old):
        if not consumed[index]:
            deltas.append(
                SectionDelta("deleted", content_hash, path, prior_node_id=node)
            )
    return deltas


def _consume(
    old: Sequence[_OldSection],
    consumed: list[bool],
    predicate: Callable[[_OldSection], bool],
) -> int | None:
    for index, entry in enumerate(old):
        if not consumed[index] and predicate(entry):
            consumed[index] = True
            return entry[3]
    return None


def _old_sections(
    conn: sqlite3.Connection, tree: str, source: str, path: str
) -> list[_OldSection]:
    rows = conn.execute(
        "SELECT id, ordinal, content_hash FROM sections "
        "WHERE source = ? AND path = ? ORDER BY ordinal, id",
        (source, path),
    ).fetchall()
    return [
        (
            int(r["id"]),
            int(r["ordinal"]),
            r["content_hash"],
            cluster_store.section_node(conn, tree, int(r["id"])),
        )
        for r in rows
    ]


def _drop_path(conn: sqlite3.Connection, source: str, path: str) -> None:
    fts.clear_path(conn, source, path)
    conn.execute(
        "DELETE FROM sections WHERE source = ? AND path = ?", (source, path)
    )
