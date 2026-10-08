"""Is this span encoded data rather than text anyone wrote? A byte sniff.

A real corpus inlines what is not source at all: base64 fonts and images in
HTML templates, a minified library under ``tests/``, a "gold file" JSON whose
values are base64 PDFs. On BC Registries 758 of 9827 sections (17% of the
bytes) were this, and they were worse than waste: asked to condense a base64
blob "copying values verbatim", the model ran out of turns once and past the
300 s call limit once, each time stopping an 8505-section build.

The baked ignore list cannot catch them, because they live in ordinary file
types under ordinary names. What they share is their SHAPE: long runs with no
whitespace at all. Text anyone writes breaks into words and lines; a URL or a
hash is a run of tens of bytes, not hundreds. A span is encoded when runs of
at least ``RUN`` such bytes make up more than ``SHARE`` of it.
"""

from __future__ import annotations

import re

RUN = 400
SHARE = 0.5

_RUN = re.compile(rb"\S{%d,}" % RUN)


def encoded(body: bytes) -> bool:
    """True when ``body`` is mostly long whitespace-free runs."""
    if not body:
        return False
    covered = sum(match.end() - match.start() for match in _RUN.finditer(body))
    return covered > SHARE * len(body)
