# ruff: noqa: E501, SIM115 - experiment harness
"""Offline: does the exported map name what a list task's items name?

For each item of each task, the identifier-like tokens of its text
(CamelCase, snake_case, dotted topic names, UPPER constants) are looked for
in the export's briefs. An item is "in one brief" when a single brief holds
all its tokens, "spread" when every token is somewhere in the export but no
one brief has them all, else "absent". A task whose items are mostly absent
is one the map cannot win, whatever the agent does; that is a brief fault.

Usage: python map_check.py <set> <export folder>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

TOKEN = re.compile(
    r"\b(?:[A-Za-z]+(?:_[A-Za-z0-9]+)+|[a-z]+(?:[A-Z][a-z0-9]+)+|[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+|[a-z]+(?:\.[a-z]+){2,}|[A-Z]{3,}(?:_[A-Z0-9]+)*)\b"
)
NOISE = {
    "POST",
    "GET",
    "PATCH",
    "PUT",
    "DELETE",
    "HTTP",
    "NATS",
    "GCP",
    "JSON",
    "JWT",
    "API",
    "URL",
    "SQL",
    "CRA",
    "PAD",
    "EFT",
    "NSF",
    "BCOL",
    "UI",
}


def tokens(text: str) -> set[str]:
    return {t for t in TOKEN.findall(text) if t not in NOISE and len(t) > 3}


def main(name: str, export: str) -> None:
    briefs = {
        p: p.read_text(errors="replace") for p in Path(export).rglob("brief.md")
    }
    whole = "\n".join(briefs.values())
    tasks = json.load(
        open(Path.home() / "hrono-deep" / "data" / f"{name}.json")
    )
    for q in tasks:
        one = spread = absent = 0
        misses = []
        for f in q["facts"]:
            toks = tokens(f["fact"])
            if not toks:
                one += 1
                continue
            if any(all(t in b for t in toks) for b in briefs.values()):
                one += 1
            elif all(t in whole for t in toks):
                spread += 1
            else:
                absent += 1
                misses.append(sorted(t for t in toks if t not in whole)[:4])
        print(
            f"{q['qid']:14} items {len(q['facts']):3}  in one brief {one:3}  spread {spread:3}  absent {absent:3}  missing e.g. {misses[:5]}"
        )


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
