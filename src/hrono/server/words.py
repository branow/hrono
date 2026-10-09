"""Small helpers for saying a count the way a person would."""

from __future__ import annotations


def counted(count: int, plural: str) -> str:
    """`1 topic`, `3 topics`: the count and its noun, agreeing.

    Takes the plural because that is what the data already carries
    (`holds_what` is "sections" or "topics"), and every noun on this page
    forms its singular by losing the final `s`.
    """
    return f"{count} {plural if count != 1 else plural.removesuffix('s')}"


def size(count: int) -> str:
    """A byte budget as a person reads it: `10 KB`, `800 B`.

    The page quotes the budgets the splitter actually uses
    (`ingest/split/constants.py`) through this, so a number on a page is the
    constant and not a copy of it that goes stale when the constant moves.
    """
    if count >= 1024 and count % 1024 == 0:
        return f"{count // 1024} KB"
    return f"{count} B"
