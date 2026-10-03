"""Where the words on the map are, so no two of them land on each other (#212).

The map is SVG drawn on the server, which means every piece of text has a
position before the page exists — so whether two labels collide is arithmetic,
and is decided here rather than left to whoever looks at the result. With the
overlays on, the review tree had "18 sections" struck through by an arc and two
"0.88 similar" labels printed over each other.

A text's box is estimated from its length: every label on the map is set in a
monospaced face (`base.html`), so a character's advance is a constant of the
font size. The estimate is deliberately a little generous.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# Advance of one character, per font on the map (`base.html`: 11.5px and
# 10.5px mono), and the height a line of either occupies around its baseline.
NAME_CHAR = 7.0
META_CHAR = 6.4
ASCENT = 9.0
DESCENT = 3.0
# A topic's three lines, as baselines below the bottom of its circle.
NAME_LINE = 15.0
PLACE_LINE = 29.0
COUNT_LINE = 43.0
# Where a topic's own furniture ends below its circle: the last line, and the
# chevron under it for a topic that opens.
TEXT_END = COUNT_LINE + DESCENT + 2
CHEVRON_END = 64.0
# How far a label is moved when every spot on its line is taken.
STEP = 14.0
TRIES = 40


@dataclass(frozen=True)
class Box:
    left: float
    top: float
    right: float
    bottom: float

    def hits(self, other: Box) -> bool:
        return not (
            self.right <= other.left
            or other.right <= self.left
            or self.bottom <= other.top
            or other.bottom <= self.top
        )

    def cut_by(
        self, start: tuple[float, float], end: tuple[float, float]
    ) -> bool:
        """Whether the straight segment ``start`` -> ``end`` passes through."""
        (x1, y1), (x2, y2) = start, end
        near, far = 0.0, 1.0
        for origin, delta, low, high in (
            (x1, x2 - x1, self.left, self.right),
            (y1, y2 - y1, self.top, self.bottom),
        ):
            if delta == 0:
                if not low < origin < high:
                    return False
                continue
            enter, leave = sorted(
                ((low - origin) / delta, (high - origin) / delta)
            )
            near, far = max(near, enter), min(far, leave)
            if near >= far:
                return False
        return True


def crosses(
    boxes: Iterable[Box], points: Sequence[tuple[float, float]]
) -> bool:
    """Whether the polyline through ``points`` runs through any of ``boxes``."""
    held = tuple(boxes)
    return any(
        box.cut_by(start, end)
        for start, end in zip(points, points[1:], strict=False)
        for box in held
        if min(start[0], end[0]) < box.right
        and box.left < max(start[0], end[0])
    )


def text(x: float, baseline: float, words: str, char: float) -> Box:
    """The box of a line of text centred on ``x``, sitting on ``baseline``."""
    half = len(words) * char / 2
    return Box(x - half, baseline - ASCENT, x + half, baseline + DESCENT)


def topic(
    x: float,
    y: float,
    radius: float,
    lines: tuple[str, str, str],
    opens: bool,
) -> tuple[Box, ...]:
    """Everything one topic draws: its circle, its three lines, its chevron."""
    name, place, count = lines
    boxes = [
        Box(x - radius, y - radius, x + radius, y + radius),
        text(x, y + radius + NAME_LINE, name, NAME_CHAR),
        text(x, y + radius + PLACE_LINE, place, META_CHAR),
        text(x, y + radius + COUNT_LINE, count, META_CHAR),
    ]
    if opens:
        boxes.append(
            Box(
                x - 14,
                y + radius + TEXT_END,
                x + 14,
                y + radius + CHEVRON_END,
            )
        )
    return tuple(box for box in boxes if box.right > box.left)


def furniture_end(y: float, radius: float, opens: bool) -> float:
    """The y below which a topic draws nothing — where an arc may leave it."""
    return y + radius + (CHEVRON_END if opens else TEXT_END) + 2


def place(
    candidates: Sequence[tuple[float, float]],
    words: str,
    taken: Iterable[Box],
) -> tuple[float, float, Box]:
    """The first candidate spot where ``words`` overlaps nothing in ``taken``.

    When every candidate is occupied the last one is walked downwards until it
    is clear, so a label is always placed and never printed over another.
    """
    held = tuple(taken)
    for x, y in candidates:
        box = text(x, y, words, META_CHAR)
        if not any(box.hits(other) for other in held):
            return x, y, box
    x, y = candidates[-1]
    for step in range(1, TRIES + 1):
        lower = y + step * STEP
        box = text(x, lower, words, META_CHAR)
        if not any(box.hits(other) for other in held):
            return x, lower, box
    return x, lower, box
