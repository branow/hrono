"""Mechanical faithfulness check on generated briefs — no LLM, deterministic.

LLM summaries can fabricate (the experiments caught an invented "512 chars"
value), so every brief is checked against the source it was reduced from by a
pure rule, not another model: extract identifier-shaped tokens (dotted names,
camelCase, PascalCase, snake_case, 3+ digit numbers) from the generated text and
verify each appears in the source; a dotted compound counts as supported when
every part does. Tokens with no support are suspected fabrications. Ported from
the prototype's ``check_faithfulness.py``.

What it deliberately does NOT treat as an identifier (#103, F22): anything
joined by a SLASH. The first port read any token containing "/" or "." as a
name, so ordinary prose — ``CI/CD``, ``tabs/spaces/line``, ``and/or``,
``binaries/packages``, ``encoding/decoding``, ``Flask/Werkzeug`` — was flagged
as fabrication. Six of seven flags on the QA corpus were prose, which makes the
verdict useless as a triage queue: a gate nobody can trust is a gate nobody
reads. A dotted abbreviation (``e.g``, ``i.e``) is an identifier by shape, so it
is excluded by name instead.
"""

from __future__ import annotations

import re

_IDENT = r"[A-Za-z_][A-Za-z0-9_]*"
_IDENTIFIER = re.compile(
    rf"\b{_IDENT}(?:\.{_IDENT})+\b"  # dotted: Signer.rsplit, base64.hex
    r"|\b[a-z]+(?:[A-Z][a-z0-9]*)+\b"  # camelCase
    r"|\b(?:[A-Z][a-z0-9]+){2,}\b"  # PascalCase (2+ humps)
    r"|\b[A-Za-z]+_[A-Za-z0-9_]+\b"  # snake_case
    r"|\b\d{3,}\b"  # numbers with 3+ digits
)
_STOPWORDS = frozenset({"e.g", "i.e", "a.k.a", "etc"})


def faithfulness(generated: str, source: str) -> tuple[str, ...]:
    """Return the identifier tokens in ``generated`` unsupported by ``source``.

    Empty means faithful. A dotted compound (``a.b``) is supported when the
    source contains it, or contains each of its parts — the source naming both
    the receiver and the member is support for the combination, where a name
    that appears nowhere is not.
    """
    source_lower = source.lower()
    missing: set[str] = set()
    for token in _IDENTIFIER.findall(generated):
        lowered = token.rstrip(".").lower()
        if lowered in _STOPWORDS or lowered in source_lower:
            continue
        parts = [part for part in lowered.split(".") if part]
        if len(parts) > 1 and all(part in source_lower for part in parts):
            continue
        missing.add(token)
    return tuple(sorted(missing))
