"""The ``split`` ingest op: turn a synced source into stored sections/passages.

For a source leaf, asks the type's READER for the source's units (#143 — git's
are the ingestable files of its synced working tree, #025/#026), splits each
into sections + passages (#029/#030), assigns identity (#031), and persists
them with content-addressed bodies (#032 store). The whole
source is replaced in one transaction (delete-by-source then insert), so a
re-split of an unchanged cache is idempotent: identical bytes reuse their
content rows and no sections are duplicated. Registers into the op registry so
the worker dispatches ``split`` per source. Reads only the local cache — no
network, no secret — so it needs no cipher.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from pathlib import Path

from hrono import pins
from hrono.cluster.blend import register_path_bodies
from hrono.ingest import SplitError, Unit, store
from hrono.ingest.identity import (
    Address,
    content_hash,
    sp_render,
    structure_paths,
)
from hrono.ingest.readers import resolve
from hrono.ingest.split import structure
from hrono.ingest.split.constants import section_budget
from hrono.ingest.split.node import Node
from hrono.ingest.split.pack import sections as pack_sections
from hrono.ingest.split.section import Section
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.recall import fts
from hrono.registry import store as registry_store


def split_source(job: Job, context: JobContext) -> Mapping[str, int]:
    """Split the job's synced source into stored sections and passages.

    Reports what the split CHANGED — files new or edited, the sections cut
    from them, files gone — so a re-split of an unchanged source, which
    rewrites every row to the same bytes, says it had nothing to do (#213).
    """
    name = str(job.scope["name"])
    config, version = _load(context, name)
    cache = context.cache_for(name)
    reader, addressed, instance = resolve(config, cache)
    cut: dict[str, tuple[str, ...]] = {}
    with context.database.write() as conn:
        before = _cut_by_path(conn, name)
        held = _held_sections(conn, name)
        store.clear_source(conn, name)
        fts.clear_source(conn, name)
        for unit in reader.units(config, cache):
            stored = store_unit(conn, unit, name, addressed, instance, version)
            cut[unit.path] = tuple(digest for _id, _ord, digest in stored)
            _repin(conn, held.get(unit.path, ()), stored)
        register_path_bodies(conn, list(cut))
    changed = [
        path for path, hashes in cut.items() if before.get(path) != hashes
    ]
    return {
        "files_changed": len(changed),
        "sections_cut": sum(len(cut[path]) for path in changed),
        "files_gone": len(before.keys() - cut.keys()),
    }


def store_unit(
    conn: sqlite3.Connection,
    unit: Unit,
    source: str,
    source_type: str,
    instance: str,
    version: str,
) -> tuple[tuple[int, int, str], ...]:
    """Split one unit into sections/passages, returning (id, ordinal, hash)."""
    path, raw = unit.path, unit.body
    tree = structure(Path(path), raw)
    address = Address(source_type, instance, path, unit.version or version)
    stored: list[tuple[int, int, str]] = []
    for ordinal, section in enumerate(sections_of(tree, path, raw)):
        section_hash = _store_body(conn, raw, section.start, section.end)
        section_id = store.insert_section(
            conn,
            source=source,
            address=address,
            start=section.start,
            end=section.end,
            content_hash=section_hash,
            ordinal=ordinal,
        )
        stored.append((section_id, ordinal, section_hash))
        for p_ordinal, passage in enumerate(section.passages):
            passage_hash = _store_body(conn, raw, passage.start, passage.end)
            paths = tuple(
                sp_render(sp)
                for sp in structure_paths(
                    tree, passage.start, passage.end, passage.part, passage.of
                )
            )
            passage_id = store.insert_passage(
                conn,
                section_id=section_id,
                source=source,
                address=address,
                start=passage.start,
                end=passage.end,
                content_hash=passage_hash,
                sp_paths=paths,
                ordinal=p_ordinal,
            )
            fts.index_passage(
                conn,
                passage_id=passage_id,
                source=source,
                path=path,
                body=raw[passage.start : passage.end].decode(
                    "utf-8", "replace"
                ),
            )
    return tuple(stored)


def sections_of(tree: Node, path: str, raw: bytes) -> tuple[Section, ...]:
    """The sections one file is cut into: the cut a split stores and an
    estimate counts, so the two cannot disagree on how many there are."""
    return pack_sections(tree, section_budget(Path(path)), raw)


#: one held section as the re-split needs it: ordinal, hash, anchor, reason
_Held = tuple[int, str, int | None, str | None]


def _held_sections(
    conn: sqlite3.Connection, source: str
) -> dict[str, tuple[_Held, ...]]:
    """Each path's membership pins, read before the re-split erases them.

    ``clear_source`` deletes every section and the 0030 trigger takes the pins
    with them, so without this snapshot every full re-split released every
    hand-placed chunk in the source — the silent revert pins exist to prevent,
    through the maintenance door instead of the update one.
    """
    rows = conn.execute(
        "SELECT s.path, s.ordinal, s.content_hash, p.anchor_id, p.reason "
        "FROM pins p JOIN sections s ON s.id = p.target_id "
        "WHERE p.kind = ? AND s.source = ? ORDER BY s.path, s.ordinal",
        (pins.MEMBERSHIP, source),
    ).fetchall()
    held: dict[str, tuple[_Held, ...]] = {}
    for row in rows:
        entry: _Held = (
            int(row["ordinal"]),
            str(row["content_hash"]),
            None if row["anchor_id"] is None else int(row["anchor_id"]),
            row["reason"],
        )
        held[row["path"]] = (*held.get(row["path"], ()), entry)
    return held


def _repin(
    conn: sqlite3.Connection,
    held: tuple[_Held, ...],
    stored: tuple[tuple[int, int, str], ...],
) -> None:
    """Re-pin a path's held sections onto their re-split successors.

    Content hash first, ordinal second — the same pairing ``reconcile`` uses —
    so an unchanged file re-pins exactly, and an edited one holds the section
    in the slot the operator pinned.
    """
    consumed: set[int] = set()
    for ordinal, digest, anchor, reason in held:
        match = next(
            (
                sid
                for sid, _, h in stored
                if h == digest and sid not in consumed
            ),
            None,
        )
        if match is None:
            match = next(
                (
                    sid
                    for sid, o, _ in stored
                    if o == ordinal and sid not in consumed
                ),
                None,
            )
        if match is None:
            continue
        consumed.add(match)
        pins.pin(conn, pins.MEMBERSHIP, match, reason=reason, anchor=anchor)


def _cut_by_path(
    conn: sqlite3.Connection, source: str
) -> dict[str, tuple[str, ...]]:
    """Each stored file's section hashes, in order: what a re-split matches."""
    rows = conn.execute(
        "SELECT path, content_hash FROM sections WHERE source = ? "
        "ORDER BY path, ordinal",
        (source,),
    ).fetchall()
    cut: dict[str, tuple[str, ...]] = {}
    for row in rows:
        cut[row["path"]] = (*cut.get(row["path"], ()), row["content_hash"])
    return cut


def _store_body(
    conn: sqlite3.Connection, raw: bytes, start: int, end: int
) -> str:
    body = raw[start:end]
    digest = content_hash(body)
    store.upsert_content(conn, digest, body)
    return digest


def _load(context: JobContext, name: str) -> tuple[dict[str, object], str]:
    with context.database.connect() as conn:
        row = registry_store.get(conn, "sources", name)
        if row is None:
            raise SplitError(f"unknown source: {name}")
        state = conn.execute(
            "SELECT version FROM source_state WHERE source = ?", (name,)
        ).fetchone()
    if state is None:
        raise SplitError(f"source not synced: {name}")
    config: dict[str, object] = json.loads(row["config"])
    return config, str(state["version"])


__all__ = ["SplitError", "split_source", "store_unit"]

OPS["split"] = split_source
