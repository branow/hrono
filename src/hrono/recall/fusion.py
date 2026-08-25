"""RRF fusion of the two recall legs (T27): weighted 70/30, k=60, cap 10.

Frozen recipe (how-hrono-works.md): union the qualified passages from the vector
leg (#072) and the keyword leg (#073) and rank them by weighted reciprocal rank
fusion

    score(p) = 0.7/(60 + vector_rank) + 0.3/(60 + keyword_rank)

contributing a term only for the leg(s) where the passage qualified, then cap at
10 hits. There is NO gap-based cutoff — the legs' z-floors alone decide
membership. Ordering is deterministic (ties break by passage id). An empty union
returns no hits and the exact explore message. All constants are baked.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

K = 60
VECTOR_WEIGHT = 0.7
KEYWORD_WEIGHT = 0.3
CAP = 10
EXPLORE_MESSAGE = "no confident matches - explore the map."


@dataclass(frozen=True)
class Fusion:
    """The fused hits (passage ids, best first) and the empty-case message."""

    hits: tuple[int, ...]
    message: str | None


def fuse(
    vector_hits: Sequence[tuple[int, float]],
    keyword_hits: Sequence[tuple[int, float]],
) -> Fusion:
    """Union + weighted-RRF-rank the two legs' passages, capped at 10."""
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
    ranked = sorted(union, key=lambda pid: (-score(pid), pid))[:CAP]
    return Fusion(
        hits=tuple(ranked),
        message=None if ranked else EXPLORE_MESSAGE,
    )
