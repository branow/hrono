"""What the Ask page remembers about a question, and the change since (#401).

The history is one cookie, so it is the browser's to send and is input: an
entry that does not parse is dropped, a cookie over ``MAX_COOKIE`` is ignored
whole, and a cookie this module writes is trimmed to fit under it. Each entry
keeps the question and a compact snapshot of what it returned (a short key per
passage, its score and a label), which is all a re-run needs to say what is
new, what moved and what dropped out. An entry from before snapshots is just
a question.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from urllib.parse import quote, unquote

from hrono.recall.engine import Hit

HISTORY = 6
MAX_COOKIE = 3800
MAX_QUESTION = 200
LABEL = 24


@dataclass(frozen=True)
class Seen:
    """One passage a past answer returned."""

    key: str
    score: float
    label: str


@dataclass(frozen=True)
class Entry:
    """A past question; ``seen`` is None when no answer was kept for it."""

    question: str
    seen: tuple[Seen, ...] | None = None


@dataclass(frozen=True)
class Change:
    """A re-run set against the last answer to the same question."""

    status: tuple[str, ...]  # per hit: "new", "same" or "moved from #n"
    dropped: tuple[tuple[int, Seen], ...]  # old rank (1-based) and passage

    @property
    def fresh(self) -> int:
        return sum(1 for s in self.status if s == "new")


def read(raw: str) -> list[Entry]:
    """The entries a cookie holds; nothing for one that is not ours."""
    if len(raw) > MAX_COOKIE:
        return []
    try:
        stored = json.loads(unquote(raw or "[]"))
    except ValueError:
        return []
    if not isinstance(stored, list):
        return []
    entries = (_entry(item) for item in stored[:HISTORY])
    return [entry for entry in entries if entry is not None]


def write(entries: list[Entry]) -> str:
    """A cookie value for ``entries``, trimmed until it fits."""
    kept = entries[:HISTORY]
    while kept:
        value = quote(
            json.dumps([_stored(e) for e in kept], separators=",:"), safe=""
        )
        if len(value) <= MAX_COOKIE:
            return value
        kept = _trim(kept)
    return quote("[]")


def snapshot(hits: tuple[Hit, ...]) -> tuple[Seen, ...]:
    return tuple(
        Seen(key(hit), round(hit.score, 3), _label(hit)) for hit in hits
    )


def key(hit: Hit) -> str:
    """A short stable name for a passage: its source version and range."""
    raw = f"{hit.uri}:{hit.start}:{hit.end}".encode()
    return hashlib.sha1(raw, usedforsecurity=False).hexdigest()[:8]


def compare(before: tuple[Seen, ...], hits: tuple[Hit, ...]) -> Change:
    """Mark each of ``hits`` new, moved or same, and list what dropped."""
    old = {seen.key: rank for rank, seen in enumerate(before, 1)}
    now = {key(hit) for hit in hits}
    status = []
    for rank, hit in enumerate(hits, 1):
        was = old.get(key(hit))
        if was is None:
            status.append("new")
        elif was == rank:
            status.append("same")
        else:
            status.append(f"moved from #{was}")
    dropped = tuple(
        (rank, seen)
        for rank, seen in enumerate(before, 1)
        if seen.key not in now
    )
    return Change(tuple(status), dropped)


def remember(
    entries: list[Entry], question: str, seen: tuple[Seen, ...] | None
) -> list[Entry]:
    """``entries`` with ``question`` newest; ``None`` keeps its last answer."""
    question = question[:MAX_QUESTION]
    if seen is None:
        seen = next((e.seen for e in entries if e.question == question), None)
    others = [e for e in entries if e.question != question]
    return [Entry(question, seen), *others][:HISTORY]


def before(entries: list[Entry], question: str) -> tuple[Seen, ...] | None:
    question = question[:MAX_QUESTION]
    return next((e.seen for e in entries if e.question == question), None)


def _trim(entries: list[Entry]) -> list[Entry]:
    """Drop the oldest answer kept; with none left, the oldest question."""
    for index in range(len(entries) - 1, -1, -1):
        if entries[index].seen is not None:
            old = entries[index]
            return [
                *entries[:index],
                Entry(old.question),
                *entries[index + 1 :],
            ]
    return entries[:-1]


def _label(hit: Hit) -> str:
    path = hit.uri.rpartition("@")[0]
    return f"{path[-LABEL:]} {hit.start}"


def _stored(entry: Entry) -> object:
    if entry.seen is None:
        return {"q": entry.question}
    return {
        "q": entry.question,
        "r": [[s.key, s.score, s.label] for s in entry.seen],
    }


def _entry(item: object) -> Entry | None:
    if isinstance(item, str):
        return Entry(item[:MAX_QUESTION])
    if not isinstance(item, dict) or not isinstance(item.get("q"), str):
        return None
    rows = item.get("r")
    if rows is None:
        return Entry(item["q"][:MAX_QUESTION])
    seen = _seen(rows)
    if seen is None:
        return Entry(item["q"][:MAX_QUESTION])
    return Entry(item["q"][:MAX_QUESTION], seen)


def _seen(rows: object) -> tuple[Seen, ...] | None:
    if not isinstance(rows, list):
        return None
    out = []
    for row in rows:
        if not (
            isinstance(row, list)
            and len(row) == 3
            and isinstance(row[0], str)
            and isinstance(row[1], int | float)
            and not isinstance(row[1], bool)
            and isinstance(row[2], str)
        ):
            return None
        score = _finite(row[1])
        if score is None:
            return None
        out.append(Seen(row[0], score, row[2]))
    return tuple(out)


def _finite(value: int | float) -> float | None:
    try:
        score = float(value)
    except OverflowError:
        return None
    return score if math.isfinite(score) else None
