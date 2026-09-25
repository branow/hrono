"""The recall engine (T28): assemble the two legs + fusion into ranked hits.

Embeds the question (content), runs the vector leg (#072) and keyword leg (#073)
over the UNION of source and brief passages, fuses them (#074), and renders up
to ``limit`` hits — each the passage's one-line header (address + ``sp:``
structure paths), full body, origin (summary for ``node`` passages, else
source), and fused score. An empty union returns no hits and the frozen explore
message. The whole recipe is internal — no constant surfaces. The query encoder
is injected so the engine is testable offline; the endpoint builds the real one.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from hrono.recall import fusion, keyword_leg, vector_leg
from hrono.recall.scope import passages_of

Encode = Callable[[list[str]], Sequence[Sequence[float]]]


@dataclass(frozen=True)
class Hit:
    uri: str
    kind: str
    header: str
    body: str
    score: float


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
    limit: int = fusion.CAP,
    tree: str | None = None,
) -> Recall:
    """Run the frozen recall recipe for ``question`` and return ranked hits.

    ``tree`` scopes the corpus to that tree's passages (#166). Omitted, or a
    tree that declares no sources, searches everything — which is what a
    single-corpus database is, and why its scores are unchanged.
    """
    query_vec = list(encode([question])[0])
    allowed = None if tree is None else passages_of(conn, tree)
    vector_z = vector_leg.scores(conn, query_vec, model_name, allowed)
    keyword_z = keyword_leg.scores(conn, question, allowed)
    vector_hits = vector_leg.qualify(vector_z, keyword_z)
    keyword_hits = keyword_leg.search(conn, question, vector_z, allowed)

    fused = fusion.fuse(
        vector_hits,
        keyword_hits,
        _documents(conn, vector_hits, keyword_hits),
    )
    if not fused.ranked:
        return Recall(hits=(), message=fused.message)

    cap = min(limit, fusion.CAP)
    hits = tuple(
        _render(conn, passage_id, score)
        for passage_id, score in fused.ranked[:cap]
    )
    return Recall(hits=hits, message=None)


def _documents(
    conn: sqlite3.Connection,
    vector_hits: Sequence[tuple[int, float]],
    keyword_hits: Sequence[tuple[int, float]],
) -> dict[int, str]:
    """Map each candidate passage to the document it belongs to (#126).

    A document is the passage's URI, which addresses the FILE and not the
    slice of it — the unit a reader would call "the same place". hrono's URIs
    carry no position (#144): every passage of a file at one version shares
    one, and where the passage sits inside it lives in ``ordinal`` and
    ``sp_paths``. So the URI IS the document key, with nothing to strip.
    """
    ids = {pid for pid, _ in vector_hits} | {pid for pid, _ in keyword_hits}
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT id, uri FROM passages WHERE id IN ({marks})",  # noqa: S608
        tuple(ids),
    ).fetchall()
    return {int(row["id"]): str(row["uri"]) for row in rows}


def _render(conn: sqlite3.Connection, passage_id: int, score: float) -> Hit:
    row = conn.execute(
        "SELECT p.uri AS uri, p.sp_paths AS sp_paths, p.source_type AS "
        "source_type, c.body AS body FROM passages p "
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
    )
