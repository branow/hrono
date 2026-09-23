"""Put a written brief into the shared passage store, addressed ``node://``.

Every brief is markdown, so it goes through the SAME splitter (#029/#030) and
the SAME passage store as source content, tagged ``source_type='node'`` and
addressed

    node://hrono/nodes/<id>/<slug>@<member-signature>

— the topic's title slug (from the brief's first line) gives the path-blend
semantics to match, and the member-set signature (#064) is the opaque version,
so a brief whose signature changed replaces its ``@<oldsig>`` passages. Brief
passages are content-addressed like source passages, so the #035 embed op
vectorises them and the #070 FTS index covers them with no extra wiring; recall
(#072-075) unions source and ``node`` passages and labels each by source_type.

MEASURED, and the premise holds (#135). A brief competes on score like any
other passage, and for the questions it is FOR it wins: on the QA corpus "give
me an overview of the architecture" returns five hits, all summaries; "what does
this project do overall" and "what are the main components of this codebase"
both put a summary in the TOP slot. For a SPECIFIC question — the signer, uuid
v7, chalk's colour levels — source passages take the whole window, which is the
right answer: a question about one function is best answered by that function.

That is worth writing down because a measurement over 22 questions once found a
brief clearing the vector floor exactly ONCE, which read as "the summary layer
never competes". Every one of those 22 was a specific question. The layer was
doing its job; the question set could not see it.

A per-node ``source`` key (``node-<id>``) scopes the replace: clearing it drops
the node's old brief section (passages cascade) and FTS rows before re-storing.
Brief sections live in ``sections`` but are excluded from clustering/condensing
by their ``source_type`` so they never become topics or get condensed.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from hrono.cluster.blend import register_path_bodies
from hrono.ingest import store
from hrono.ingest.identity import (
    Address,
    content_hash,
    sp_render,
    structure_paths,
)
from hrono.ingest.split import structure
from hrono.ingest.split.constants import section_budget
from hrono.ingest.split.pack import sections as pack_sections
from hrono.recall import fts

SOURCE_TYPE = "node"


def store_brief(
    conn: sqlite3.Connection,
    node_id: int,
    brief_text: str,
    member_signature: str,
) -> None:
    """(Re)store a node's brief as ``node://`` passages in the passage store."""
    slug = _slug(brief_text)
    source = f"node-{node_id}"
    path = f"nodes/{node_id}/{slug}"
    address = Address(SOURCE_TYPE, "hrono", path, member_signature)

    store.clear_source(
        conn, source
    )  # drop old brief section (passages cascade)
    fts.clear_source(conn, source)
    register_path_bodies(conn, [path])

    raw = brief_text.encode("utf-8")
    grammar = Path(f"{slug}.md")
    tree = structure(grammar, raw)
    for ordinal, section in enumerate(
        pack_sections(tree, section_budget(grammar), raw)
    ):
        section_hash = _body(conn, raw, section.start, section.end)
        section_id = store.insert_section(
            conn,
            source=source,
            address=address,
            start=section.start,
            end=section.end,
            content_hash=section_hash,
            ordinal=ordinal,
        )
        for p_ordinal, passage in enumerate(section.passages):
            passage_hash = _body(conn, raw, passage.start, passage.end)
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


def _body(conn: sqlite3.Connection, raw: bytes, start: int, end: int) -> str:
    body = raw[start:end]
    digest = content_hash(body)
    store.upsert_content(conn, digest, body)
    return digest


def _slug(text: str) -> str:
    stripped = text.strip()
    first = stripped.splitlines()[0].lstrip("#").strip() if stripped else ""
    slug = re.sub(r"[^a-z0-9]+", "-", first.lower()).strip("-")
    return slug[:60] or "node"
