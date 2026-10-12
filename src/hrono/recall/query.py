"""What recall embeds: the question, a sentence at a time.

A prompt is split at sentence ends and line breaks; a piece of fewer than
``SHORTEST`` words (a heading, a list marker) joins nothing and is dropped.
A prompt with no sentence long enough is embedded whole.
"""

from __future__ import annotations

import re

SHORTEST = 3
_BREAK = re.compile(r"(?<=[.?!:])\s+|\n+")


def sentences(question: str) -> list[str]:
    """The sentences of ``question`` worth embedding, or the question whole."""
    parts = [part.strip() for part in _BREAK.split(question)]
    kept = [part for part in parts if len(part.split()) >= SHORTEST]
    return kept or [question]
