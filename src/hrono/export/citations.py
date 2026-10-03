"""Link a brief's concrete facts to the section pages that settle them (E018).

A brief states TAU 0.70, an env var, a size — and the agent that reads it
cannot name the file that says so, so it cites the brief, which cannot be
checked (E004: 10 of 12 walk-only failures were a right answer citing
``root.md``). The brief is stored as the model wrote it; the export puts the
link back in code, from the member sections the renderer already holds, so no
link is ever written by the model and none can point at a page that is not
there.

A fact is a token that names something: a backticked span, an UPPER_SNAKE
name, a decimal, a number with a unit, a number of two digits or more. It is
cited only when it occurs in at most ``_MOST`` of the sections offered — a
token found in most of them settles nothing in particular.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Collection, Mapping, Sequence

_MOST = 3
_PER_LINE = 2
_FACT = re.compile(
    r"`(?P<code>[^`\n]{2,40})`"
    r"|(?P<name>\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b)"
    r"|(?P<number>\b\d+\.\d+\b|\b\d+\s?(?:KB|MB|GB|B|ms)\b|\b\d{2,}\b)"
)
_WORD = re.compile(r"[\w.]+")
_RUN = _WORD
_NOT_PROSE = ("#", "|", "```")


class FactIndex:
    """Where each fact occurs in the corpus, worked out once.

    A render cites every brief line of every node, and the same fact recurs up
    the tree; scanning every section for it each time made a 268-file export
    take eight seconds (E018 qa). Each section is split into words once, a fact
    that is a single word is a dictionary lookup, and the answer is for the
    whole corpus, so a node's own subtree is a filter over it.
    """

    def __init__(self, pages: Mapping[str, str]) -> None:
        self._pages = pages
        self._words: dict[str, list[str]] | None = None
        self._found: dict[str, tuple[str, ...]] = {}

    def homes(
        self, fact: str, within: Collection[str] | None = None
    ) -> list[str]:
        """The sections stating ``fact``, only those in ``within`` if given."""
        found = self._found.get(fact)
        if found is None:
            found = self._found[fact] = self._search(fact)
        if within is None:
            return list(found)
        return [label for label in found if label in within]

    def _search(self, fact: str) -> tuple[str, ...]:
        if _WORD.fullmatch(fact):
            return tuple(self._index().get(fact, ()))
        pattern = re.compile(rf"(?<![\w.]){re.escape(fact)}(?![\w])")
        return tuple(
            label
            for label, body in self._pages.items()
            if fact in body and pattern.search(body)
        )

    def _index(self) -> dict[str, list[str]]:
        if self._words is None:
            words: dict[str, list[str]] = {}
            for label, body in self._pages.items():
                for word in _words(body):
                    words.setdefault(word, []).append(label)
            self._words = words
        return self._words


def _words(body: str) -> set[str]:
    """Every run of word characters and dots, and its head before each dot.

    A fact that is one such run matches where it starts a run and what follows
    it is not a word character, which is a dot or the end of the run: "60"
    is in "60.5" and "60." but not in "160" or "v1.60".
    """
    found: set[str] = set()
    for run in _RUN.findall(body):
        found.add(run)
        found.update(run[:at] for at in range(1, len(run)) if run[at] == ".")
    return found


def cite(
    text: str,
    pages: Mapping[str, str] | FactIndex,
    *,
    link: Callable[[str], str],
    within: Collection[str] | None = None,
) -> str:
    """``text`` with, on each line stating facts, links to where they live.

    ``pages`` maps a section's label to its body (or is the ``FactIndex`` of
    them, shared across calls); ``link`` gives the path to link a label by,
    relative to the page being written; ``within`` limits the sections offered.
    """
    index = pages if isinstance(pages, FactIndex) else FactIndex(pages)
    out: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        out.append(
            line
            if fenced or line.lstrip().startswith(_NOT_PROSE)
            else _cited(line, index, link, within)
        )
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _cited(
    line: str,
    index: FactIndex,
    link: Callable[[str], str],
    within: Collection[str] | None,
) -> str:
    found: dict[str, int] = {}
    for fact in _facts(line):
        homes = index.homes(fact, within)
        if not homes or len(homes) > _MOST:
            continue
        for label in homes:
            found[label] = found.get(label, 0) + 1
    if not found:
        return line
    ranked = sorted(found, key=lambda label: (-found[label], label))
    links = ", ".join(f"[§]({link(label)})" for label in ranked[:_PER_LINE])
    return f"{line.rstrip()} ({links})"


def _facts(line: str) -> Sequence[str]:
    seen: dict[str, None] = {}
    for match in _FACT.finditer(line):
        seen[
            match.group("code") or match.group("name") or match.group("number")
        ] = None
    return tuple(seen)
