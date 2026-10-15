"""What a run actually DID, as sentences a person can act on.

Every op returns a result dict, and this renders it. A green `succeeded` and
a token count alone would report a sync that split two topics, judged
nothing, and left the tree one `settle` short of finished exactly as a sync
that did nothing at all, leaving the operator with two new topics on the map
and no way to find out why.

Three things are read out of one result, and they are different questions:

- **what happened** — the counts, with the zeros dropped. A line per thing that
  actually occurred, because "dissolved 0, split 2, migrated 0, freed 0" is a
  result nobody reads to the end of.
- **what it measured** — the rates and flags that are findings rather than
  actions, kept even when they are zero: a misfit rate of 0 is an answer.
- **what to do next** — the whole reason this module is not a `pre` tag. A
  result carries `settle_due`, `above_baseline` and `incomplete`, each meaning
  "this run finished and the tree still needs something".

The vocabulary is DATA, keyed by the field name the ops already emit. A new op
reporting `reparented` gets a sentence by adding a row here, and an op
reporting something nobody has named still renders — humanised from its own
key — rather than vanishing.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from hrono.server import i18n

# One line per counted thing: the field an op emits -> how to say it, as
# (singular, plural). The count goes in front.
COUNTED: dict[str, tuple[str, str]] = {
    "condensed": ("section condensed", "sections condensed"),
    "briefed": ("brief written", "briefs written"),
    "written": ("brief written", "briefs written"),
    "embedded": ("piece of text embedded", "pieces of text embedded"),
    "fetched": ("new version fetched", "new versions fetched"),
    "files_changed": ("new or changed file read", "new or changed files read"),
    "sections_cut": ("section cut", "sections cut"),
    "files_gone": ("file gone from the source", "files gone from the source"),
    "sections": ("section read", "sections read"),
    "files": ("file read", "files read"),
    "levels": ("level", "levels"),
    "nodes": ("topic made", "topics made"),
    "topics": ("topic made", "topics made"),
    "judged": ("topic judged", "topics judged"),
    "propagated": ("brief marked stale", "briefs marked stale"),
    "abstained": (
        "topic the judge could not answer for",
        "topics the judge could not answer for",
    ),
    "skipped": ("topic skipped", "topics skipped"),
    "skipped_pinned": ("held by hand, left alone", "held by hand, left alone"),
    "forced": (
        "section filed with no good fit",
        "sections filed with no good fit",
    ),
    "parked": ("section waiting for a topic", "sections waiting for a topic"),
    "placed": ("section placed", "sections placed"),
    "moved": ("section re-filed", "sections re-filed"),
    "split": ("topic split in two", "topics split in two"),
    "dissolved": ("topic retired", "topics retired"),
    "migrated": (
        "section moved to a better topic",
        "sections moved to a better topic",
    ),
    "reparented": (
        "topic hung under a new parent",
        "topics hung under a new parent",
    ),
    "freed": ("pin released", "pins released"),
    "pinned": ("hand edit left alone", "hand edits left alone"),
    "removed": ("item removed", "items removed"),
    "topics_added": ("topic added to the map", "topics added to the map"),
    "topics_removed": (
        "topic taken off the map",
        "topics taken off the map",
    ),
    "sections_refiled": (
        "section re-filed under another topic",
        "sections re-filed under another topic",
    ),
    "briefs_rewritten": ("brief written", "briefs written"),
    "refused": (
        "reply that was not a summary, not kept",
        "replies that were not summaries, not kept",
    ),
    "adopted": (
        "new topic hung back under the tree",
        "new topics hung back under the tree",
    ),
}

# Findings rather than actions: printed even at zero, because the number IS the
# answer to the question the stage was asked.
MEASURED: dict[str, str] = {
    "misfit_rate": "misfit rate",
    "drift": "drift since the last settle",
}

# "This run is over and the tree still wants something." Each maps the flag to
# what it means and which op answers it.
NEXT: dict[str, tuple[str, str]] = {
    "settle_due": (
        "Sections have been waiting long enough to be worth placing.",
        "settle",
    ),
    "above_baseline": (
        "More sections sit closer to another topic than the tree was built "
        "with. A rebuild would re-file them.",
        "settle",
    ),
    "incomplete": (
        "A stage stopped before it finished everything it had.",
        "",
    ),
}

# A result key the outcome lines must NOT carry: either a grouping heading
# with nothing of its own, or something the page already prints in its own
# column. `input`/`output` are the token counts, and `_flat` lifts them out of
# `tokens` — without naming them here a run reported "10 input, 2 output" as
# two of the things it did.
QUIET = frozenset({"tokens", "repaired", "changed", "input", "output"})


@dataclass(frozen=True)
class Outcome:
    """One run's result, split into the three questions it answers."""

    did: list[str] = field(default_factory=list)
    found: list[str] = field(default_factory=list)
    next: list[dict[str, str]] = field(default_factory=list)
    quiet: bool = False

    @property
    def anything(self) -> bool:
        return bool(self.did or self.found or self.next)


def read(result: Mapping[str, object] | None) -> Outcome:
    """Turn one op's result into what it did, found, and leaves to be done."""
    if not result:
        return Outcome()
    flat = _flat(result)
    did = [
        _counted(key, int(value))
        for key, value in flat.items()
        if key in COUNTED and _is_count(value) and int(value) > 0
    ]
    found = [
        _measured(key, value)
        for key, value in flat.items()
        if key in MEASURED and isinstance(value, (int, float))
    ]
    did += [
        _unnamed(key, int(value))
        for key, value in flat.items()
        if key not in COUNTED
        and key not in MEASURED
        and key not in NEXT
        and key not in QUIET
        and _is_count(value)
        and int(value) > 0
    ]
    return Outcome(
        did=sorted(did),
        found=found,
        next=[
            {"says": i18n.gettext(NEXT[key][0]), "op": NEXT[key][1]}
            for key, value in flat.items()
            if key in NEXT and value is True
        ],
        # a run that changed nothing is the DESIGN working, and saying so beats
        # an empty panel the reader reads as "the page is broken"
        quiet=not did and not found,
    )


def _flat(result: Mapping[str, object]) -> dict[str, object]:
    """One level of nesting folded in — `repaired: {split: 2}` is `split: 2`.

    The nesting groups the fields for the API; for a reader it is a second
    heading over one number each.
    """
    flat: dict[str, object] = {}
    for key, value in result.items():
        if isinstance(value, Mapping):
            flat.update(_flat(value))
        else:
            flat[key] = value
    return flat


def _is_count(value: object) -> bool:
    """Counts only: `True` is an `int` in Python and is not two of a thing."""
    return isinstance(value, int) and not isinstance(value, bool)


def _counted(key: str, count: int) -> str:
    singular, plural = COUNTED[key]
    return i18n.ngettext(count, "{n} " + singular, "{n} " + plural)


def _unnamed(key: str, count: int) -> str:
    """A field nobody has written a sentence for, said as well as it can be.

    An op that reports something new shows it rather than dropping it — the
    missing row here is a cosmetic gap, and a silently missing number is not.
    """
    return f"{count} {key.replace('_', ' ')}"


def _measured(key: str, value: object) -> str:
    if key == "misfit_rate":
        return i18n.gettext(
            "misfit rate {rate}", rate=f"{float(value) * 100:.1f}%"
        )
    if key == "drift":
        return i18n.gettext("drift since the last settle {drift}", drift=value)
    return f"{MEASURED[key]} {value}"
