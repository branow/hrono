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
) -> Recall:
    """Run the frozen recall recipe for ``question`` and return ranked hits."""
    query_vec = list(encode([question])[0])
    vector_z = vector_leg.scores(conn, query_vec, model_name)
    vector_hits = tuple(
        sorted(
            (
                (pid, z)
                for pid, z in vector_z.items()
                if z >= vector_leg.Z_FLOOR
            ),
            key=lambda hit: hit[1],
            reverse=True,
        )
    )
    keyword_hits = keyword_leg.search(conn, question, vector_z)

    fused = fusion.fuse(vector_hits, keyword_hits)
    if not fused.ranked:
        return Recall(hits=(), message=fused.message)

    cap = min(limit, fusion.CAP)
    hits = tuple(
        _render(conn, passage_id, score)
        for passage_id, score in fused.ranked[:cap]
    )
    return Recall(hits=hits, message=None)


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
