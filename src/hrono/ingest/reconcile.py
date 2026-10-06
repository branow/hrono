"""Apply a file-level diff to the section store, section by section (#085, T34).

The bridge between #083's file diff and the #085 placement rule: it mutates only
the sections of the changed files (untouched files keep their sections and their
cluster membership untouched) and returns the section-level deltas the placement
rule consumes — each carrying the PRIOR cluster of the chunk it replaces so the
sticky re-check has a target. Matching new sections to old is by CONTENT HASH
first (an unchanged section inside an edited file maps to itself and stays put),
then by ordinal for the genuinely edited slots; an old section left unmatched is
a deletion.

The bytes of a changed unit come from ``fetch``, the source reader's
by-path lookup (#143), so this path is no more filesystem-bound than the full
split is.

A changed/deleted/moved file's old sections are dropped (their memberships
cascade away); the placement rule re-attaches the survivors. Bodies are stored
by content hash, so a moved file's content is reused and never re-embedded.
Each delta therefore carries the membership its predecessor HAD — node,
similarity, forced flag, and the incubator batch if it was parked — because
once the old row is gone that is the only record of it, and a rename has to be
re-attached on exactly those terms (#100).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from hrono import pins
from hrono.cluster import incubator
from hrono.cluster import store as cluster_store
from hrono.cluster.blend import register_path_bodies
from hrono.cluster.placement import SectionDelta
from hrono.ingest.diff import Change
from hrono.ingest.readers import Unit
from hrono.ingest.split_op import store_unit
from hrono.recall import fts


@dataclass(frozen=True)
class _Old:
    """One superseded section: its identity and where it sat in the tree."""

    section_id: int
    ordinal: int
    content_hash: str
    member: cluster_store.Membership | None
    batch: int | None  # the batch it was parked at, if it was pending
    pin: tuple[int | None, str | None] | None  # (anchor, reason) if held


def reconcile(
    conn: sqlite3.Connection,
    *,
    tree: str,
    source: str,
    source_type: str,
    instance: str,
    version: str,
    fetch: Callable[[str], Unit],
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
                fetch,
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
    fetch: Callable[[str], Unit],
    change: Change,
) -> list[SectionDelta]:
    if change.status == "new":
        stored = store_unit(
            conn,
            fetch(change.path),
            source,
            source_type,
            instance,
            version,
        )
        return [
            SectionDelta("new", h, change.path, section_id=sid)
            for sid, _, h in stored
        ]
    if change.status == "deleted":
        old = _old_sections(conn, tree, source, change.path)
        _drop_path(conn, source, change.path)
        return [
            SectionDelta(
                "deleted",
                entry.content_hash,
                change.path,
                prior_node_id=_node(entry),
            )
            for entry in old
        ]
    old_path = change.old_path if change.status == "moved" else change.path
    kind = "moved" if change.status == "moved" else "changed"
    old = _old_sections(conn, tree, source, old_path)
    _drop_path(conn, source, old_path)
    stored = store_unit(
        conn, fetch(change.path), source, source_type, instance, version
    )
    deltas = _match(kind, change.path, old, stored)
    _carry_pins(conn, old, deltas)
    return deltas


def _carry_pins(
    conn: sqlite3.Connection,
    old: Sequence[_Old],
    deltas: Sequence[SectionDelta],
) -> None:
    """Re-pin each held section onto the section that replaced it (#154).

    The pins trigger (0030) deleted the old row's pin with the row, so the
    operator's hold exists only in ``old`` now. A delta that matched a pinned
    predecessor carries its anchor; this writes the hold back under the new id
    — same anchor, same reason — so an edit to a pinned file does not release
    what a human placed.
    """
    reasons = {
        entry.pin[0]: entry.pin[1]
        for entry in old
        if entry.pin is not None and entry.pin[0] is not None
    }
    for delta in deltas:
        if delta.section_id is None or delta.pinned_anchor is None:
            continue
        pins.pin(
            conn,
            pins.MEMBERSHIP,
            delta.section_id,
            reason=reasons.get(delta.pinned_anchor),
            anchor=delta.pinned_anchor,
        )


def _match(
    kind: str,
    path: str,
    old: Sequence[_Old],
    stored: Sequence[tuple[int, int, str]],
) -> list[SectionDelta]:
    """Pair new sections with the ones they replace, hash first then ordinal.

    A ``moved`` file's bytes are identical by definition, so its sections pair
    by CONTENT HASH — which is what lets placement keep them in place (#100).
    The exception is a rename that changes the extension: the file then splits
    under a different grammar, so a section pairs by ordinal instead and is a
    genuine ``changed`` for placement, not a move.
    """
    consumed = [False] * len(old)
    deltas: list[SectionDelta] = []
    for section_id, ordinal, content_hash in stored:
        prior = _consume(
            old, consumed, lambda e, h=content_hash: e.content_hash == h
        )
        same_content = prior is not None
        if prior is None:
            prior = _consume(old, consumed, lambda e, o=ordinal: e.ordinal == o)
        member = prior.member if prior is not None else None
        pin = prior.pin if prior is not None else None
        deltas.append(
            SectionDelta(
                kind if same_content else "changed",
                content_hash,
                path,
                section_id=section_id,
                prior_node_id=None if member is None else member.node_id,
                prior_similarity=None if member is None else member.similarity,
                prior_forced=member is not None and member.forced,
                prior_batch=prior.batch if prior is not None else None,
                pinned_anchor=None if pin is None else pin[0],
            )
        )
    for index, entry in enumerate(old):
        if not consumed[index]:
            deltas.append(
                SectionDelta(
                    "deleted",
                    entry.content_hash,
                    path,
                    prior_node_id=_node(entry),
                )
            )
    return deltas


def _node(entry: _Old) -> int | None:
    return None if entry.member is None else entry.member.node_id


def _consume(
    old: Sequence[_Old],
    consumed: list[bool],
    predicate: Callable[[_Old], bool],
) -> _Old | None:
    for index, entry in enumerate(old):
        if not consumed[index] and predicate(entry):
            consumed[index] = True
            return entry
    return None


def _old_sections(
    conn: sqlite3.Connection, tree: str, source: str, path: str
) -> list[_Old]:
    rows = conn.execute(
        "SELECT id, ordinal, content_hash FROM sections "
        "WHERE source = ? AND path = ? ORDER BY ordinal, id",
        (source, path),
    ).fetchall()
    held = pins.held_for(conn, pins.MEMBERSHIP, (int(r["id"]) for r in rows))
    return [
        _Old(
            section_id=int(r["id"]),
            ordinal=int(r["ordinal"]),
            content_hash=r["content_hash"],
            member=cluster_store.membership(conn, tree, int(r["id"])),
            batch=incubator.parked_batch(conn, tree, int(r["id"])),
            pin=held.get(int(r["id"])),
        )
        for r in rows
    ]


def _drop_path(conn: sqlite3.Connection, source: str, path: str) -> None:
    fts.clear_path(conn, source, path)
    conn.execute(
        "DELETE FROM sections WHERE source = ? AND path = ?", (source, path)
    )
