"""Grow structure for spans the parser gave no children for.

A structureless span (a no-grammar file, or a parsed leaf over the passage
budget) is deepened by the fixed delimiter cascade: split on the current
delimiter, then recurse into any piece still over budget. A level that yields
fewer than two pieces is skipped in favour of the next, so deepening never
produces a pointless single child. Splits keep the delimiter with the preceding
piece, so the pieces tile the span exactly (no gaps, no overlaps).
"""

from __future__ import annotations

from hrono.ingest.split.constants import CASCADE, PASSAGE_BYTES
from hrono.ingest.split.node import Node


def deepen(
    raw: bytes, start: int, end: int, level: int = 0
) -> tuple[Node, ...]:
    """Return synthetic children tiling ``[start, end)``, or () if none fit."""
    if level >= len(CASCADE):
        return ()
    delimiter = CASCADE[level]
    pieces = _split(raw, start, end, delimiter.separator)
    if len(pieces) < 2:
        return deepen(raw, start, end, level + 1)
    return tuple(
        Node(
            piece_start,
            piece_end,
            f"~{delimiter.name}",
            None,
            deepen(raw, piece_start, piece_end, level + 1)
            if piece_end - piece_start > PASSAGE_BYTES
            else (),
        )
        for piece_start, piece_end in pieces
    )


def _split(
    raw: bytes, start: int, end: int, separator: bytes
) -> tuple[tuple[int, int], ...]:
    spans: list[tuple[int, int]] = []
    pos = start
    search = start
    while True:
        found = raw.find(separator, search, end)
        if found == -1:
            break
        piece_end = found + len(separator)
        spans.append((pos, piece_end))
        pos = piece_end
        search = piece_end
    if pos < end:
        spans.append((pos, end))
    return tuple(spans)
