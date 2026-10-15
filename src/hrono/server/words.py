"""Small helpers for saying a count the way a person would."""

from __future__ import annotations

from hrono.server.i18n import ngettext


def counted(count: int, plural: str) -> str:
    """`1 topic`, `3 topics`: the count and its noun, agreeing.

    Takes the plural because that is what the data already carries
    (`holds_what` is "sections" or "topics"), and every noun on this page
    forms its singular by losing the final `s`. In Ukrainian the noun takes
    one of three forms, from the catalog's ``"{n} topic|{n} topics"``.
    """
    singular = plural.removesuffix("s")
    return ngettext(count, f"{{n}} {singular}", f"{{n}} {plural}")


def size(count: int) -> str:
    """A byte budget as a person reads it: `10 KB`, `800 B`.

    The page quotes the budgets the splitter actually uses
    (`ingest/split/constants.py`) through this, so a number on a page is the
    constant and not a copy of it that goes stale when the constant moves.
    """
    if count >= 1024 and count % 1024 == 0:
        return f"{count // 1024} KB"
    return f"{count} B"


def weight(count: int) -> str:
    """A measured byte total, rounded the way a person reads it: `31.3 MB`.

    Unlike ``size``, which quotes a budget exactly, this is for a total the
    page counted; its last digits are noise to the reader.
    """
    if count >= 1024 * 1024:
        return f"{count / (1024 * 1024):.1f} MB"
    if count >= 1024:
        return f"{round(count / 1024)} KB"
    return f"{count} B"


def compact(count: int) -> str:
    """A large count at a glance: `4.79M`, `14.1k`, `812`.

    For a table of totals, where seven-digit figures side by side are read as
    their size; the exact figure goes in the cell's title.
    """
    for scale, unit in ((1_000_000_000, "B"), (1_000_000, "M"), (1_000, "k")):
        if count >= scale:
            value = count / scale
            digits = 2 if value < 10 else 1 if value < 100 else 0
            return f"{value:.{digits}f}{unit}"
    return str(count)
