"""Recall's window: the topics that both legs and both lanes agree on.

Two legs rank every passage: cosine of the question's embedding and BM25 of
its words. Two lanes hold them: brief passages and source passages. Each
lane fuses its two legs by reciprocal rank (1 / (k + rank), k 60), so a
passage needs no calibrated floor to count, and a leaf is scored by its
best brief passage plus its best source passage. A leaf whose brief reads
like the question and whose code carries its words beats a file that
matches once by luck: a test or a generated document has a peak in one
lane and nothing in the other, so it loses without anyone naming it.

The hit a leaf shows is whichever of its two lane bests reads most like
the question: its brief for an overview question, the matching slice for
a question that names a line of code. A passage no leaf holds (a tree not
built yet) is its own group, keyed by its file. The window is never
padded: a ranking that runs out comes back short.

Measured on the bcreg tree against 15 hard questions' fact leaves
(evaluations/2026-10-defines-uses/harness/recall_formulas.py): with 5 hits,
42 of 111 facts have a leaf among them against 26 for plain cosine, one per
file; with 15 hits, 75 against 49.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

CAP = 20
DEPTH = 2000  # ranks each leg contributes to the fusion
RRF_K = 60
EXPLORE_MESSAGE = "no confident matches - explore the map."
BRIEF = "brief"
SOURCE = "source"

# a passage's lane and group: ("brief", "topic:7") or ("source", "topic:7")
# or ("source", "<uri>") for a passage no leaf holds
Lanes = Callable[[Sequence[int]], dict[int, tuple[str, str]]]


def window(
    by_cosine: Sequence[tuple[int, float]],
    by_words: Sequence[int],
    lanes_of: Lanes,
    limit: int = CAP,
) -> tuple[tuple[int, float], ...]:
    """The best ``limit`` groups, each as the passage that speaks for it.

    ``by_cosine`` is (passage id, cosine) best first, ``by_words`` passage
    ids best first; ``lanes_of`` maps ids to their lane and group in one
    batch. The passage that speaks for a group is the one of its two lane
    bests that reads most like the question (the higher cosine): a brief
    for an overview question, the matching slice for a question that
    names a line of code.
    """
    size = min(limit, CAP)
    closeness = dict(by_cosine[:DEPTH])
    cosine = list(closeness)
    words = list(by_words[:DEPTH])
    lanes = lanes_of(sorted(set(cosine) | set(words)))
    # (group, lane) -> (score, passage): the lane's best passage of the group
    best: dict[tuple[str, str], tuple[float, int]] = {}
    for lane in (BRIEF, SOURCE):
        fused: dict[int, float] = {}
        for leg in (cosine, words):
            rank = 0
            for pid in leg:
                placed = lanes.get(pid)
                if placed is None or placed[0] != lane:
                    continue
                rank += 1
                fused[pid] = fused.get(pid, 0.0) + 1.0 / (RRF_K + rank)
        for pid, score in fused.items():
            key = (lanes[pid][1], lane)
            if key not in best or (score, -pid) > (
                best[key][0],
                -best[key][1],
            ):
                best[key] = (score, pid)
    groups: dict[str, float] = {}
    for (group, _lane), (score, _pid) in best.items():
        groups[group] = groups.get(group, 0.0) + score
    shown: list[tuple[int, float]] = []
    # a tie goes to the group with a brief: it states the part, a source
    # slice only shows it
    order = sorted(
        groups,
        key=lambda g: (-groups[g], (g, BRIEF) not in best, _first(best, g)),
    )
    for group in order:
        voices = [
            best[k][1] for k in ((group, BRIEF), (group, SOURCE)) if k in best
        ]
        voice = max(voices, key=lambda pid: (closeness.get(pid, -1.0), -pid))
        shown.append((voice, groups[group]))
        if len(shown) == size:
            break
    return tuple(shown)


def _first(best: dict[tuple[str, str], tuple[float, int]], group: str) -> int:
    """The lowest passage id of a group: a deterministic tie-break."""
    return min(pid for (g, _lane), (_score, pid) in best.items() if g == group)
