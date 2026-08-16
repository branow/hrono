"""Sections and passages: the two leaf granularities hrono stores.

A section is the clustering and traversal unit; a passage is the recall
injection unit. A section's passages tile it exactly, so a section is the
byte-identical concatenation of its passages, and the sections tile the whole
file. Passages byte-chopped from an atomic over-budget span carry their raw
``part``/``of`` index so identity (#031) can render a raw sp-path tail; ordinary
passages leave both None.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Passage:
    """A recall-injection span; ``part``/``of`` set only when byte-chopped."""

    start: int
    end: int
    part: int | None = None
    of: int | None = None


@dataclass(frozen=True)
class Section:
    """A clustering/traversal span holding its ordered, nested passages."""

    start: int
    end: int
    passages: tuple[Passage, ...]
