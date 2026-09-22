"""RRF fusion of the two recall legs (T27): weighted 70/30, k=60, cap 10.

Frozen recipe (how-hrono-works.md): union the qualified passages from the vector
leg (#072) and the keyword leg (#073) and rank them by weighted reciprocal rank
fusion

    score(p) = 0.7/(60 + vector_rank) + 0.3/(60 + keyword_rank)

contributing a term only for the leg(s) where the passage qualified, then cap at
10 hits. There is NO gap-based cutoff — the legs' z-floors alone decide
membership. Ordering is deterministic (ties break by passage id). An empty union
returns no hits and the exact explore message. All constants are baked.

DIVERSITY IS A RESERVE, NOT A CAP (#126). The window used to have no notion of
where its hits came from, so one document could fill all ten. A hard per-doc
cap was rejected because it cannot tell "this document IS the answer" from "this
document is hogging the window" — "generate a version 7 uuid" answers from one
file, and truncating it to make room for worse hits elsewhere serves a metric
rather than a reader. So a document may take more than its share of the window
only once no OTHER document has a qualifying hit left unplaced: every candidate
gets its turn first, and the leader keeps whatever is still empty afterwards.
Nothing unqualified is ever added — the backfill draws only from passages that
already cleared a leg's floor, so a window that cannot be filled from distinct
documents comes back short rather than padded.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

K = 60
VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
CAP = 10
MAX_DOCUMENT_SHARE = 0.4  # one document's reserve of the window (#126)
EXPLORE_MESSAGE = "no confident matches - explore the map."


@dataclass(frozen=True)
class Fusion:
    """The fused (passage id, score) ranking and the empty-case message."""

    ranked: tuple[tuple[int, float], ...]
    message: str | None

    @property
    def hits(self) -> tuple[int, ...]:
        """The ranked passage ids, best first."""
        return tuple(passage_id for passage_id, _ in self.ranked)


def fuse(
    vector_hits: Sequence[tuple[int, float]],
    keyword_hits: Sequence[tuple[int, float]],
    documents: Mapping[int, str] | None = None,
) -> Fusion:
    """Union + weighted-RRF-rank the two legs' passages, capped at 10.

    ``documents`` maps a passage to the document it belongs to and turns on the
    diversity reserve; without it the window is pure score order (#126).
    """
    vector_rank = {pid: i + 1 for i, (pid, _) in enumerate(vector_hits)}
    keyword_rank = {pid: i + 1 for i, (pid, _) in enumerate(keyword_hits)}

    def score(passage_id: int) -> float:
        total = 0.0
        if passage_id in vector_rank:
            total += VECTOR_WEIGHT / (K + vector_rank[passage_id])
        if passage_id in keyword_rank:
            total += KEYWORD_WEIGHT / (K + keyword_rank[passage_id])
        return total

    union = set(vector_rank) | set(keyword_rank)
    ordered = sorted(union, key=lambda pid: (-score(pid), pid))
    window = _reserve(ordered, documents) if documents else ordered[:CAP]
    ranked = tuple((pid, score(pid)) for pid in window)
    return Fusion(ranked=ranked, message=None if ranked else EXPLORE_MESSAGE)


def _reserve(
    ordered: Sequence[int], documents: Mapping[int, str]
) -> tuple[int, ...]:
    """Fill the window in score order, holding back a dominant document (#126).

    One pass places up to each document's share; a passage past its document's
    share is DEFERRED, not dropped. The deferred pool then fills whatever the
    first pass left empty, so the only way a document exceeds its share is that
    nobody else wanted the slot.
    """
    share = max(1, int(CAP * MAX_DOCUMENT_SHARE))
    placed: list[int] = []
    deferred: list[int] = []
    taken: dict[str, int] = {}
    for passage_id in ordered:
        document = documents.get(passage_id)
        if document is None or taken.get(document, 0) < share:
            if document is not None:
                taken[document] = taken.get(document, 0) + 1
            placed.append(passage_id)
        else:
            deferred.append(passage_id)
        if len(placed) == CAP:
            return tuple(placed)
    return tuple(placed + deferred[: CAP - len(placed)])
