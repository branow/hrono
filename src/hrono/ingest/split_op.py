"""The ``split`` ingest op: turn a synced source into stored sections/passages.

For a source leaf, reads the source's synced cache (#025), filters the candidate
files (#026), splits each into sections + passages (#029/#030), assigns identity
(#031), and persists them with content-addressed bodies (#032 store). The whole
source is replaced in one transaction (delete-by-source then insert), so a
re-split of an unchanged cache is idempotent: identical bytes reuse their
content rows and no sections are duplicated. Registers into the op registry so
the worker dispatches ``split`` per source. Reads only the local cache — no
network, no secret — so it needs no cipher.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from hrono.cluster.blend import register_path_bodies
from hrono.ingest import store
from hrono.ingest.filter import ingestable
from hrono.ingest.identity import (
    Address,
    content_hash,
    sp_render,
    structure_paths,
)
from hrono.ingest.split import structure
from hrono.ingest.split.constants import section_budget
from hrono.ingest.split.pack import sections as pack_sections
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.recall import fts
from hrono.registry import store as registry_store

_CACHE_ROOT = Path(".hrono/cache/sources")


class SplitError(Exception):
    """A source could not be split (reason is credential-free)."""


def split_source(job: Job, context: JobContext) -> None:
    """Split the job's synced source into stored sections and passages."""
    name = str(job.scope["name"])
    config, version = _load(context, name)
    source_type = str(config["type"])
    instance = _instance(str(config["url"]))
    filter_config = config.get("filter")
    cache = _CACHE_ROOT / name
    files = ingestable(
        cache, filter_config if isinstance(filter_config, dict) else None
    )
    with context.database.connect() as conn, conn:
        store.clear_source(conn, name)
        fts.clear_source(conn, name)
        register_path_bodies(conn, files)
        for path in files:
            store_file(conn, cache, path, name, source_type, instance, version)


def store_file(
    conn: sqlite3.Connection,
    cache: Path,
    path: str,
    source: str,
    source_type: str,
    instance: str,
    version: str,
) -> tuple[tuple[int, int, str], ...]:
    """Split one file into sections/passages, returning (id, ordinal, hash)."""
    raw = (cache / path).read_bytes()
    tree = structure(Path(path), raw)
    address = Address(source_type, instance, path, version)
    stored: list[tuple[int, int, str]] = []
    for ordinal, section in enumerate(
        pack_sections(tree, section_budget(Path(path)))
    ):
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


def _instance(url: str) -> str:
    text = url.strip()
    if "://" in text:
        text = text.split("://", 1)[1]
    head = text.split("/", 1)[0]
    if "@" in head:
        text = text[text.index("@") + 1 :]
    text = text.rstrip("/")
    if text.endswith(".git"):
        text = text[:-4]
    slash = text.find("/")
    colon = text.find(":")
    if colon != -1 and (slash == -1 or colon < slash):
        text = text[:colon] + "/" + text[colon + 1 :]
    return text


OPS["split"] = split_source
