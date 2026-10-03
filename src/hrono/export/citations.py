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
from collections.abc import Mapping, Sequence

_MOST = 3
_PER_LINE = 2
_FACT = re.compile(
    r"`(?P<code>[^`\n]{2,40})`"
    r"|(?P<name>\b[A-Z][A-Z0-9]*_[A-Z0-9_]+\b)"
    r"|(?P<number>\b\d+\.\d+\b|\b\d+\s?(?:KB|MB|GB|B|ms)\b|\b\d{2,}\b)"
)
_NOT_PROSE = ("#", "|", "```")


def cite(
    text: str,
    pages: Mapping[str, str],
    *,
    link: Mapping[str, str],
) -> str:
    """``text`` with, on each line stating facts, links to where they live.

    ``pages`` maps a section's label to its body; ``link`` maps the same label
    to the path to link it by, relative to the page being written.
    """
    out: list[str] = []
    fenced = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        out.append(
            line
            if fenced or line.lstrip().startswith(_NOT_PROSE)
            else _cited(line, pages, link)
        )
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _cited(line: str, pages: Mapping[str, str], link: Mapping[str, str]) -> str:
    found: dict[str, int] = {}
    for fact in _facts(line):
        homes = _homes(fact, pages)
        if not homes or len(homes) > _MOST:
            continue
        for label in homes:
            found[label] = found.get(label, 0) + 1
    if not found:
        return line
    ranked = sorted(found, key=lambda label: (-found[label], label))
    links = ", ".join(f"[§]({link[label]})" for label in ranked[:_PER_LINE])
    return f"{line.rstrip()} ({links})"


def _facts(line: str) -> Sequence[str]:
    seen: dict[str, None] = {}
    for match in _FACT.finditer(line):
        seen[
            match.group("code") or match.group("name") or match.group("number")
        ] = None
    return tuple(seen)


def _homes(fact: str, pages: Mapping[str, str]) -> list[str]:
    pattern = re.compile(rf"(?<![\w.]){re.escape(fact)}(?![\w])")
    return [label for label, body in pages.items() if pattern.search(body)]
