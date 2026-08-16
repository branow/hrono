"""Baked splitting budgets and the synthetic-delimiter cascade.

These are operating constants from the settled recipe, not config: the passage
budget below which a span needs no deepening, and the ordered delimiter cascade
the splitter grows structure with. The packer's own budgets (sections,
tiny-merge) land with the packer.
"""

from __future__ import annotations

from dataclasses import dataclass

PARAGRAPH_BYTES = 800


@dataclass(frozen=True)
class Delimiter:
    """One cascade level: a display name and the bytes it splits on."""

    name: str
    separator: bytes


CASCADE: tuple[Delimiter, ...] = (
    Delimiter("blank-line", b"\n\n"),
    Delimiter("line", b"\n"),
    Delimiter("sentence", b". "),
    Delimiter("comma", b","),
    Delimiter("word", b" "),
)
