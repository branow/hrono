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
import re
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from hrono.recall import gate, query, similarity
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
    pages: bool = False,
) -> Recall:
    """Recall ``question``: the passages most like it, one per document.

    ``tree`` scopes the corpus to that tree's passages. Omitted, or a tree that
    declares no sources, searches everything — which is what a single-corpus
    database is.

    ``pages`` keeps one passage per leaf topic instead: the map pages to read
    first, each with the passage that put it there. A question spanning
    several services needs more facts than five passages hold, and the leaf
    briefs state them; a passage that is a test, or an upper brief, points
    at no page.
    """
    allowed = None if tree is None else passages_of(conn, tree)
    if not gate.answers(conn, question, allowed):
        return Recall(hits=(), message=EXPLORE_MESSAGE)
    query_vecs = [list(vector) for vector in encode(query.sentences(question))]
    ranked = similarity.ranked(conn, query_vecs, model_name, allowed)
    keys = _pages if pages else _documents
    kept = window(ranked, lambda ids: keys(conn, ids, tree), limit)
    if not kept:
        return Recall(hits=(), message=EXPLORE_MESSAGE)
    hits = tuple(
        _render(conn, passage_id, score, tree) for passage_id, score in kept
    )
    return Recall(hits=hits, message=None)


def _documents(
    conn: sqlite3.Connection, ids: Sequence[int], tree: str | None = None
) -> dict[int, str | None]:
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


TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__)/|(^|/)test_[^/]*$|_test\.\w+$|\.(spec|test)\.\w+$"
)


def _pages(
    conn: sqlite3.Connection, ids: Sequence[int], tree: str | None
) -> dict[int, str | None]:
    """Map each passage to the leaf topic it sits on, or None.

    A source passage sits on the leaf holding its section; a leaf brief's
    passage on that leaf. A test, an upper brief, and a section no leaf
    holds have no page.
    """
    if not ids:
        return {}
    rows = conn.execute(
        "SELECT p.id, p.source_type, p.source, p.path, "
        "(SELECT MIN(m.node_id) FROM node_members m "
        " JOIN nodes n ON n.id = m.node_id WHERE m.section_id = p.section_id "
        " AND n.level = 0 AND (? IS NULL OR n.tree = ?)) AS leaf "
        "FROM passages p WHERE p.id IN (SELECT value FROM json_each(?))",
        (tree, tree, json.dumps(list(ids))),
    ).fetchall()
    out: dict[int, str | None] = {}
    for row in rows:
        if row["source_type"] == "node":
            node = int(str(row["source"]).removeprefix("node-"))
            level = conn.execute(
                "SELECT level FROM nodes WHERE id = ?", (node,)
            ).fetchone()
            leaf = node if level is not None and level["level"] == 0 else None
        else:
            path = str(row["path"] or "")
            leaf = None if TEST_PATH.search(path) else row["leaf"]
        out[int(row["id"])] = None if leaf is None else f"topic:{leaf}"
    return out


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
