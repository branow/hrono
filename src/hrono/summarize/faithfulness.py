"""Mechanical faithfulness check on generated briefs — no LLM, deterministic.

LLM summaries can fabricate (the experiments caught an invented "512 chars"
value), so every brief is checked against the source it was reduced from by a
pure rule, not another model: extract identifier-like tokens (camelCase,
PascalCase, dotted/path compounds, snake_case, 3+ digit numbers) from the
generated text and verify each appears literally (case-insensitive) in the
source; a slash-joined prose compound counts as supported when every part is.
Tokens with no support are suspected fabrications. Ported clean from the
prototype's ``check_faithfulness.py`` — the rules are settled, not re-derived.
"""

from __future__ import annotations

import re

_IDENTIFIER = re.compile(
    r"[A-Za-z_][A-Za-z0-9_]*(?:[./][A-Za-z0-9_$#{}-]+)+"  # dotted/path
    r"|\b[a-z]+(?:[A-Z][a-z0-9]*)+\b"  # camelCase
    r"|\b(?:[A-Z][a-z0-9]+){2,}\b"  # PascalCase (2+ humps)
    r"|\b[A-Za-z]+_[A-Za-z0-9_]+\b"  # snake_case
    r"|\b\d{3,}\b"  # numbers with 3+ digits
)


def faithfulness(generated: str, source: str) -> tuple[str, ...]:
    """Return the identifier tokens in ``generated`` unsupported by ``source``.

    Empty means faithful. A slash-compound (``a/b``) is supported when each
    part is; a trailing dot is ignored.
    """
    source_lower = source.lower()
    missing: set[str] = set()
    for token in _IDENTIFIER.findall(generated):
        parts = [part for part in token.rstrip(".").split("/") if part]
        if all(part.lower() in source_lower for part in parts):
            continue
        missing.add(token)
    return tuple(sorted(missing))
