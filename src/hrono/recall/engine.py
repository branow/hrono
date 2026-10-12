"""The recall engine: gate, rank, window, render.

A question the tree has no words for gets no hits and the explore message
(``gate``). Otherwise the question is embedded, every source and brief
passage in the tree is ranked by cosine against it (``similarity``), and the
best ``limit`` are kept, one per document (``window``). Each hit renders as the
passage's one-line header (address + ``sp:`` structure paths), full body,
origin (summary for ``node`` passages, else source), and cosine. The query
encoder is injected so the engine is testable offline; the endpoint builds
the real one.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from hrono.recall import gate, similarity
from hrono.recall.scope import passages_of
from hrono.recall.window import CAP, EXPLORE_MESSAGE, window

Encode = Callable[[list[str]], Sequence[Sequence[float]]]


@dataclass(frozen=True)
class Hit:
    uri: str
    kind: str
    header: str
    body: str
    score: float
    start: int  # byte range of the passage in its file
    end: int
    topic: int | None  # the topic holding it; a brief's own topic
    path: str = ""  # the file, relative to its source's repository
    source: str = ""  # the source it was read from


@dataclass(frozen=True)
class Recall:
    hits: tuple[Hit, ...]
    message: str | None


def recall(
    conn: sqlite3.Connection,
    question: str,
    model_name: str,
    encode: Encode,
    *,
    limit: int = CAP,
    tree: str | None = None,
) -> Recall:
    """Recall ``question``: the passages most like it, one per document.

    ``tree`` scopes the corpus to that tree's passages. Omitted, or a tree that
    declares no sources, searches everything — which is what a single-corpus
    database is.
    """
    allowed = None if tree is None else passages_of(conn, tree)
    if not gate.answers(conn, question, allowed):
        return Recall(hits=(), message=EXPLORE_MESSAGE)
    query_vec = list(encode([question])[0])
    ranked = similarity.ranked(conn, query_vec, model_name, allowed)
    kept = window(ranked, lambda ids: _documents(conn, ids), limit)
    if not kept:
        return Recall(hits=(), message=EXPLORE_MESSAGE)
    hits = tuple(
        _render(conn, passage_id, score, tree) for passage_id, score in kept
    )
    return Recall(hits=hits, message=None)


def _documents(conn: sqlite3.Connection, ids: Sequence[int]) -> dict[int, str]:
    """Map each passage to the document it belongs to: its URI.

    hrono's URIs address the FILE (or the brief), not the slice of it: every
    passage of a file at one version shares one, and where the passage sits
    inside it lives in ``ordinal`` and ``sp_paths``. So the URI IS the document
    key, with nothing to strip.
    """
    if not ids:
        return {}
    rows = conn.execute(
        "SELECT id, uri FROM passages "
        "WHERE id IN (SELECT value FROM json_each(?))",
        (json.dumps(list(ids)),),
    ).fetchall()
    return {int(row["id"]): str(row["uri"]) for row in rows}


def _render(
    conn: sqlite3.Connection, passage_id: int, score: float, tree: str | None
) -> Hit:
    row = conn.execute(
        "SELECT p.uri AS uri, p.sp_paths AS sp_paths, p.source_type AS "
        "source_type, p.source AS source, p.section_id AS section_id, "
        "p.byte_start AS start, p.byte_end AS end, p.path AS path, "
        "c.body AS body "
        "FROM passages p "
        "JOIN contents c ON c.content_hash = p.content_hash WHERE p.id = ?",
        (passage_id,),
    ).fetchone()
    sp_paths = json.loads(row["sp_paths"])
    header = " ".join([row["uri"], *sp_paths])
    kind = "summary" if row["source_type"] == "node" else "source"
    return Hit(
        uri=row["uri"],
        kind=kind,
        header=header,
        body=bytes(row["body"]).decode("utf-8", "replace"),
        score=score,
        start=int(row["start"]),
        end=int(row["end"]),
        topic=_topic(conn, row, tree),
        path=str(row["path"] or ""),
        source=str(row["source"] or ""),
    )


def _topic(
    conn: sqlite3.Connection, row: sqlite3.Row, tree: str | None
) -> int | None:
    """Where a hit sits on the map: a brief's own topic, or its section's."""
    if row["source_type"] == "node":
        return int(str(row["source"]).removeprefix("node-"))
    held = conn.execute(
        "SELECT MIN(m.node_id) AS node FROM node_members m "
        "JOIN nodes n ON n.id = m.node_id "
        "WHERE m.section_id = ? AND (? IS NULL OR n.tree = ?)",
        (row["section_id"], tree, tree),
    ).fetchone()
    return None if held["node"] is None else int(held["node"])
