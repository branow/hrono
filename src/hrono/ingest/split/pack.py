"""The greedy two-budget packer over the structure tree.

One greedy mechanism runs at two budgets: the file's category section budget to
form sections, then the passage budget inside each section's node group to form
its passages, so passages nest inside sections and a section is the
byte-identical concatenation of its passages. Consecutive whole nodes accumulate
while they fit; a node over budget is descended into; an atomic span with no
structure is byte-chopped into raw parts; a crumb under ``MIN_PARA`` merges into
its neighbour. Because the structure tree tiles every parent exactly, sibling
ends meet with no gaps, so the packed spans cover the file with no gaps or
overlaps.

A group is flushed by the BUDGET and nothing else. Flushing a passage group
as soon as it reaches ``MIN_GROUP`` (100 B), on the reading that "a decent
structural unit stands alone", caps passages at a tenth of their budget: a real
corpus packs to a 152 B median with 68% under 200 B, so a recall hit is a
truncated sentence instead of the ~200-token unit the budget describes, and the
passage table is several times larger than intended. The settled recipe
(``structure-split.ipynb:pack_node`` in ``docs/research/prototype/``) has no
such flush, and neither does this.

``_chop`` backs off to the nearest whitespace within ``_CHOP_BACKOFF`` of the
budget before cutting an atomic span, so a raw part is never a mid-token
fragment such as ``b'tColor = '``. The backoff needs the file bytes, which is
why ``sections`` takes them.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from hrono.ingest.split.constants import (
    MIN_PARA,
    PASSAGE_BYTES,
    section_budget,
)
from hrono.ingest.split.node import Node
from hrono.ingest.split.section import Passage, Section
from hrono.ingest.split.tree import structure

_CHOP_BACKOFF = 0.1  # of the budget: how far a chop may walk back for a token
_WHITESPACE = frozenset(b" \t\n\r\f\v")


@dataclass(frozen=True)
class _Span:
    start: int
    end: int
    nodes: tuple[Node, ...]
    part: int | None = None
    of: int | None = None


def split(path: Path, raw: bytes) -> tuple[Section, ...]:
    """Split a file into ordered sections, each holding its ordered passages."""
    if not raw:
        return ()
    return sections(structure(path, raw), section_budget(path), raw)


def sections(root: Node, budget: int, raw: bytes) -> tuple[Section, ...]:
    """Pack the structure tree into sections that each nest their passages.

    ``raw`` is the file's bytes: the packer reads them only to choose where to
    cut an atomic span, never to decide structure.
    """
    packed = _merge_tiny(_pack(root, budget, raw))
    return tuple(
        Section(span.start, span.end, _passages(span, raw)) for span in packed
    )


def _passages(section: _Span, raw: bytes) -> tuple[Passage, ...]:
    wrapper = Node(
        section.start, section.end, "~section", None, _group(section)
    )
    packed = _pack(wrapper, PASSAGE_BYTES, raw)
    stretched = _stretch(packed, section.start, section.end)
    merged = _merge_tiny(stretched, cap=PASSAGE_BYTES)
    bounded = _enforce_budget(merged, raw)
    return tuple(Passage(s.start, s.end, s.part, s.of) for s in bounded)


def _enforce_budget(spans: tuple[_Span, ...], raw: bytes) -> tuple[_Span, ...]:
    """Byte-chop any span over the passage budget, whatever its node coverage.

    A section can span bytes its nodes do not cover: when a crumb-merge folds a
    byte-chopped atomic span's parts away, ``_stretch`` and the final group
    flush can balloon one passage to the whole section. This is the last-resort
    guarantee that every passage stays within budget, chopping over-budget
    atomic content into ``part``/``of``-marked pieces regardless of coverage.
    """
    bounded: list[_Span] = []
    for span in spans:
        if span.end - span.start > PASSAGE_BYTES:
            bounded.extend(_chop(span.start, span.end, PASSAGE_BYTES, raw))
        else:
            bounded.append(span)
    return tuple(bounded)


def _group(section: _Span) -> tuple[Node, ...]:
    if len(section.nodes) == 1:
        return section.nodes[0].children
    return section.nodes


def _pack(node: Node, budget: int, raw: bytes) -> tuple[_Span, ...]:
    kids = node.children
    if not kids:
        return _chop(node.start, node.end, budget, raw)

    spans: list[_Span] = []
    start: int | None = None
    group: list[Node] = []

    def flush(end: int) -> None:
        nonlocal start, group
        if start is None:
            return
        spans.append(_Span(start, end, tuple(group)))
        start, group = None, []

    for child in kids:
        if child.end - child.start > budget:
            flush(child.start)
            spans.extend(_pack(child, budget, raw))
            continue
        if start is None:
            start, group = child.start, [child]
        elif child.end - start > budget:
            flush(child.start)
            start, group = child.start, [child]
        else:
            group.append(child)
    flush(node.end)
    return tuple(spans)


def _chop(start: int, end: int, budget: int, raw: bytes) -> tuple[_Span, ...]:
    """Cut [start, end) into even parts within budget, on a whitespace edge.

    The parts are EVEN rather than budget-then-remainder: the target is
    recomputed from what is left over how many cuts remain, so 813 bytes become
    407/406 and not 800 + a 13-byte crumb no later pass can fold away. Each cut
    then walks back to just after the last whitespace byte within
    ``_CHOP_BACKOFF`` of that target, so a part ends at a token boundary instead
    of mid-identifier. Both the target and the backed-off cut are at most
    one budget from the cursor, so no part can exceed the budget; with no
    whitespace in the window the target stands, so progress is guaranteed.
    """
    if end <= start:
        return ()
    edges: list[tuple[int, int]] = []
    cursor = start
    while end - cursor > budget:
        parts = -(-(end - cursor) // budget)  # ceil: parts still to cut
        target = -(-(end - cursor) // parts)  # even-sized, never over budget
        cut = max(_token_edge(raw, cursor + target, budget), cursor + 1)
        edges.append((cursor, cut))
        cursor = cut
    edges.append((cursor, end))
    count = len(edges)
    return tuple(
        _Span(lo, hi, (), index + 1, count)
        for index, (lo, hi) in enumerate(edges)
    )


def _token_edge(raw: bytes, hard: int, budget: int) -> int:
    window = raw[hard - int(budget * _CHOP_BACKOFF) : hard]
    for offset, byte in enumerate(reversed(window), start=1):
        if byte in _WHITESPACE:
            return hard - offset + 1
    return hard


def _merge_tiny(
    spans: tuple[_Span, ...],
    min_para: int = MIN_PARA,
    cap: int | None = None,
) -> tuple[_Span, ...]:
    """Fold a sub-``min_para`` crumb into a neighbour, within ``cap``.

    Without the cap a crumb could push its neighbour over the passage budget,
    and the budget backstop then byte-CHOPPED that neighbour — turning a
    structural group of siblings into raw parts (a class header crumb did
    exactly this). A crumb that cannot be folded stays its own small passage,
    which costs one short passage instead of the structure of a full one.
    """

    def fits(start: int, end: int) -> bool:
        return cap is None or end - start <= cap

    out: list[_Span] = []
    for span in spans:
        prev = out[-1] if out else None
        if (
            prev is not None
            and span.end - span.start < min_para
            and fits(prev.start, span.end)
        ):
            out[-1] = replace(prev, end=span.end, nodes=prev.nodes + span.nodes)
        else:
            out.append(span)
    if (
        len(out) > 1
        and out[0].end - out[0].start < min_para
        and fits(out[0].start, out[1].end)
    ):
        merged = replace(
            out[1], start=out[0].start, nodes=out[0].nodes + out[1].nodes
        )
        out = [merged, *out[2:]]
    return tuple(out)


def _stretch(
    spans: tuple[_Span, ...], start: int, end: int
) -> tuple[_Span, ...]:
    if not spans:
        return (_Span(start, end, ()),)
    first = replace(spans[0], start=start)
    body = (first, *spans[1:])
    return (*body[:-1], replace(body[-1], end=end))
