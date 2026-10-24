"""The recall engine: gate, rank by two legs, window by topic, render.

A question the tree has no words for gets no hits and the explore message
(``gate``). Otherwise every source and brief passage in the tree is ranked
twice, by cosine against the question's embedding (``similarity``) and by
BM25 over its words (``keywords``); the window fuses the two by rank in
each lane, brief passages and source passages, and keeps the best
``limit`` topics, each spoken for by one passage (``window``). Each hit
renders as the passage's one-line header (address + ``sp:`` structure
paths), full body, origin (summary for ``node`` passages, else source), and
the topic's fused score. The query encoder is injected so the engine is
testable offline; the endpoint builds the real one.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from hrono.recall import gate, keywords, query, similarity
from hrono.recall.scope import passages_of
from hrono.recall.window import (
    BRIEF,
    CAP,
    DEPTH,
    EXPLORE_MESSAGE,
    SOURCE,
    window,
)

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
    """Recall ``question``: the topics most like it, one passage each.

    ``tree`` scopes the corpus to that tree's passages. Omitted, or a tree that
    declares no sources, searches everything — which is what a single-corpus
    database is.
    """
    allowed = None if tree is None else passages_of(conn, tree)
    if not gate.answers(conn, question, allowed):
        return Recall(hits=(), message=EXPLORE_MESSAGE)
    query_vecs = [list(vector) for vector in encode(query.sentences(question))]
    by_cosine = similarity.ranked(conn, query_vecs, model_name, allowed)[:DEPTH]
    by_words = keywords.ranked(conn, question, allowed, DEPTH)
    kept = window(
        by_cosine, by_words, lambda ids: _lanes(conn, ids, tree), limit
    )
    if not kept:
        return Recall(hits=(), message=EXPLORE_MESSAGE)
    hits = tuple(
        _render(conn, passage_id, score, tree) for passage_id, score in kept
    )
    return Recall(hits=hits, message=None)


def _lanes(
    conn: sqlite3.Connection, ids: Sequence[int], tree: str | None
) -> dict[int, tuple[str, str]]:
    """Each passage's lane and group.

    A brief passage is in the brief lane, grouped by its own topic. A source
    passage is in the source lane, grouped by the leaf holding its section,
    or by its URI when no leaf holds it yet. hrono's URIs address the FILE
    (or the brief), not the slice: every passage of a file at one version
    shares one, and where the passage sits lives in ``ordinal`` and
    ``sp_paths``, so the URI is the document key with nothing to strip.
    """
    if not ids:
        return {}
    rows = conn.execute(
        "SELECT p.id, p.source_type, p.source, p.uri, "
        "(SELECT MIN(m.node_id) FROM node_members m "
        " JOIN nodes n ON n.id = m.node_id WHERE m.section_id = p.section_id "
        " AND n.level = 0 AND (? IS NULL OR n.tree = ?)) AS leaf "
        "FROM passages p WHERE p.id IN (SELECT value FROM json_each(?))",
        (tree, tree, json.dumps(list(ids))),
    ).fetchall()
    out: dict[int, tuple[str, str]] = {}
    for row in rows:
        if row["source_type"] == "node":
            node = str(row["source"]).removeprefix("node-")
            out[int(row["id"])] = (BRIEF, f"topic:{node}")
        elif row["leaf"] is not None:
            out[int(row["id"])] = (SOURCE, f"topic:{int(row['leaf'])}")
        else:
            out[int(row["id"])] = (SOURCE, str(row["uri"]))
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
