"""Recall's window: the best passages, one per document.

A document is a passage's URI, which addresses the file (or the brief), not
the slice: every passage of one file shares it. The window takes the ranked
passages in order and keeps the first of each document, so five hits are
five places to look rather than five slices of one file. It is never padded:
a ranking that runs out comes back short.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

CAP = 10
EXPLORE_MESSAGE = "no confident matches - explore the map."


def window(
    ranked: Sequence[tuple[int, float]],
    document_of: Callable[[Sequence[int]], dict[int, str]],
    limit: int = CAP,
) -> tuple[tuple[int, float], ...]:
    """The first ``limit`` passages of ``ranked``, one per document.

    ``document_of`` maps passage ids to documents; it is asked for one batch
    at a time, so a window over a large tree reads only the head of the
    ranking.
    """
    size = min(limit, CAP)
    placed: list[tuple[int, float]] = []
    seen: set[str] = set()
    batch = max(size * 5, 50)
    for start in range(0, len(ranked), batch):
        chunk = ranked[start : start + batch]
        documents = document_of([pid for pid, _ in chunk])
        for passage_id, score in chunk:
            document = documents.get(passage_id, f"passage:{passage_id}")
            if document in seen:
                continue
            seen.add(document)
            placed.append((passage_id, score))
            if len(placed) == size:
                return tuple(placed)
    return tuple(placed)
