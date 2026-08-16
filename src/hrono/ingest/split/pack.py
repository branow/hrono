"""The greedy two-budget packer over the #029 structure tree.

One greedy mechanism runs at two budgets: the file's category section budget to
form sections, then the passage budget inside each section's node group to form
its passages, so passages nest inside sections and a section is the
byte-identical concatenation of its passages. Consecutive whole nodes accumulate
while they fit; a node over budget is descended into; an atomic span with no
structure is byte-chopped into raw parts; a sibling group that reaches
``MIN_GROUP`` stands alone at its boundary; a crumb under ``MIN_PARA`` merges
into its neighbour. Because #029 tiles every parent exactly, sibling ends meet
with no gaps, so the packed spans cover the file with no gaps or overlaps.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from hrono.ingest.split.constants import (
    MIN_GROUP,
    MIN_PARA,
    PASSAGE_BYTES,
    section_budget,
)
from hrono.ingest.split.node import Node
from hrono.ingest.split.section import Passage, Section
from hrono.ingest.split.tree import structure


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
    return sections(structure(path, raw), section_budget(path))


def sections(root: Node, budget: int) -> tuple[Section, ...]:
    """Pack the structure tree into sections that each nest their passages."""
    packed = _merge_tiny(_pack(root, budget))
    return tuple(
        Section(span.start, span.end, _passages(span)) for span in packed
    )


def _passages(section: _Span) -> tuple[Passage, ...]:
    wrapper = Node(
        section.start, section.end, "~section", None, _group(section)
    )
    packed = _merge_tiny(_pack(wrapper, PASSAGE_BYTES, MIN_GROUP))
    stretched = _stretch(packed, section.start, section.end)
    return tuple(Passage(s.start, s.end, s.part, s.of) for s in stretched)


def _group(section: _Span) -> tuple[Node, ...]:
    if len(section.nodes) == 1:
        return section.nodes[0].children
    return section.nodes


def _pack(
    node: Node, budget: int, min_group: int | None = None
) -> tuple[_Span, ...]:
    limit = budget if min_group is None else min_group
    kids = node.children
    if not kids:
        return _chop(node.start, node.end, budget)

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
            spans.extend(_pack(child, budget, min_group))
            continue
        if start is None:
            start, group = child.start, [child]
        elif child.end - start > budget:
            flush(child.start)
            start, group = child.start, [child]
        else:
            group.append(child)
        if child.end - start >= limit:
            flush(child.end)
    flush(node.end)
    return tuple(spans)


def _chop(start: int, end: int, budget: int) -> tuple[_Span, ...]:
    if end <= start:
        return ()
    edges = list(range(start, end, budget))
    count = len(edges)
    return tuple(
        _Span(edge, min(edge + budget, end), (), index + 1, count)
        for index, edge in enumerate(edges)
    )


def _merge_tiny(
    spans: tuple[_Span, ...], min_para: int = MIN_PARA
) -> tuple[_Span, ...]:
    out: list[_Span] = []
    for span in spans:
        if out and span.end - span.start < min_para:
            prev = out[-1]
            out[-1] = replace(prev, end=span.end, nodes=prev.nodes + span.nodes)
        else:
            out.append(span)
    if len(out) > 1 and out[0].end - out[0].start < min_para:
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
