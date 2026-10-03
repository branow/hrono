"""Collapse the deep stored tree to <= N agent-facing levels (T29, #204).

Pure and deterministic (no LLM, no I/O): given the stored tree (each node's
level, the node->child-node edges, and each leaf node's sections) and a target
``levels`` N — the HOP LIMIT, since an agent reads the root page and then
follows one link per level down to a section file — keep N stored levels,
always including the root level and stored level 0 (whose nodes carry the
sections), and re-parent across the skipped levels so each kept node's agent
children are its descendants at the next kept level. A tree already within N
levels is returned as-is (no padding).

WHICH levels survive is a trade of depth for width (#204). Skipping a level
moves its children onto the page above, and the arithmetic of even spacing
says nothing about how many: one kept topic could list hundreds of children,
and a page an agent cannot scan costs as much as a hop too many. So every
selection that fits the hop limit is scored by the pages it would produce and
the one whose WIDEST page is smallest wins; ties go to the flatter profile,
then to the lower levels, so the answer is a function of the tree alone.

``WIDTH`` is the page budget, the number of entries one index page should list.
An entry is a title (80 chars), a one-line summary (160) and a link, about 250
bytes; 40 of them are 10 KB, the size of one SECTION — the traversal unit the
whole design is sized on (`ingest.split.constants`). So an index page costs an
agent no more to read than one section does. When no selection fits, the hop
limit holds and the shape says so: ``Shape.within_budget`` is False.

A stored edge that JUMPS a level (an orphan attached straight to a higher
topic) is followed, not dropped: a child below the level being collected is
taken where it is when its own level is kept, and looked through when it is
not, so every stored section stays reachable from the root.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from itertools import combinations

WIDTH = 40


@dataclass(frozen=True)
class StoredTree:
    """The stored tree as pure data (loaded by the caller, not read here)."""

    root: int
    node_level: Mapping[int, int]
    children: Mapping[int, Sequence[int]]
    sections: Mapping[int, Sequence[int]]


@dataclass(frozen=True)
class ExportNode:
    node_id: int
    level: int  # agent-facing level, 0 = root
    children: tuple[int, ...]  # agent child node ids (empty for a leaf)
    sections: tuple[int, ...]  # section ids (only for leaf agent nodes)


@dataclass(frozen=True)
class ExportTree:
    root: int
    levels: int  # actual agent-facing level count
    nodes: Mapping[int, ExportNode]


def collapse(stored: StoredTree, levels: int) -> ExportTree:
    """Map the stored tree to an agent-facing tree of at most ``levels``.

    ``levels`` below 2 is clamped to 2 — an export always has at least a root
    and a leaf level (there is no narrow-root/wide-leaf shape in one), so the
    function stays total over any int.
    """
    levels = max(2, levels)
    present = sorted(set(stored.node_level.values()))
    kept = present if len(present) <= levels else _narrowest(stored, levels)
    kept_desc = sorted(kept, reverse=True)  # [root_level, ..., 0]
    agent_level = {level: i for i, level in enumerate(kept_desc)}
    leaf_level = kept_desc[-1]
    kept_set = frozenset(kept_desc)

    nodes: dict[int, ExportNode] = {}
    for stored_level in kept_desc:
        below = _next_lower(kept_desc, stored_level)
        for node in _at_level(stored, stored_level):
            if below is None:
                children: tuple[int, ...] = ()
                sections = tuple(stored.sections.get(node, ()))
            else:
                children = tuple(
                    found
                    for child in stored.children.get(node, ())
                    for found in _reach(stored, child, below, kept_set)
                )
                sections = ()
            nodes[node] = ExportNode(
                node_id=node,
                level=agent_level[stored_level],
                children=children,
                sections=sections if stored_level == leaf_level else (),
            )
    return ExportTree(root=stored.root, levels=len(kept_desc), nodes=nodes)


@dataclass(frozen=True)
class Shape:
    """What an export looks like to the agent that reads it (#204)."""

    levels: int
    pages_per_level: tuple[int, ...]  # index pages, root level first
    widest_page: int  # most entries any one page lists
    widest_node: int
    width_budget: int
    within_budget: bool


def shape(tree: ExportTree) -> Shape:
    """Measure ``tree``: pages per level, and the widest page's entry count."""
    reachable = _reachable(tree)
    per_level = [0] * tree.levels
    for node_id in reachable:
        per_level[tree.nodes[node_id].level] += 1
    widths = {
        node_id: len(tree.nodes[node_id].children)
        + len(tree.nodes[node_id].sections)
        for node_id in reachable
    }
    widest = max(sorted(widths), key=lambda node_id: widths[node_id])
    return Shape(
        levels=tree.levels,
        pages_per_level=tuple(per_level),
        widest_page=widths[widest],
        widest_node=widest,
        width_budget=WIDTH,
        within_budget=widths[widest] <= WIDTH,
    )


def _narrowest(stored: StoredTree, levels: int) -> list[int]:
    """The ``levels`` stored levels whose index pages come out narrowest.

    The root level and level 0 are always kept; every choice of the levels
    between is scored by the widest index page it would make, measured with
    ``_frontier`` — how many nodes a page at level a lists when the next kept
    level is b.
    """
    present = sorted(set(stored.node_level.values()))
    top, bottom = present[-1], present[0]
    inner = present[1:-1]
    frontier = _frontier(stored)
    by_level = {level: _at_level(stored, level) for level in present[1:]}

    def widths(kept: tuple[int, ...]) -> tuple[int, ...]:
        desc = sorted(kept, reverse=True)
        return tuple(
            sorted(
                (
                    max((frontier(n, low) for n in by_level[high]), default=0)
                    for high, low in zip(desc, desc[1:], strict=False)
                ),
                reverse=True,
            )
        )

    choices = [
        (bottom, *middle, top) for middle in combinations(inner, levels - 2)
    ]
    best = min(choices, key=lambda kept: (widths(kept), kept))
    return list(best)


def _frontier(stored: StoredTree) -> Callable[[int, int], int]:
    """``count(node, b)``: the nodes a page for ``node`` lists down to ``b``.

    The first node at or below level ``b`` on each path, which is what the
    page lists when ``b`` is kept — independent of which other levels are, so
    it is computed once per (node, level) however many selections are scored.
    """

    @cache
    def count(node: int, below: int) -> int:
        return sum(
            1 if stored.node_level[child] <= below else count(child, below)
            for child in stored.children.get(node, ())
        )

    return count


def _next_lower(kept_desc: list[int], level: int) -> int | None:
    i = kept_desc.index(level)
    return kept_desc[i + 1] if i + 1 < len(kept_desc) else None


def _at_level(stored: StoredTree, level: int) -> list[int]:
    return sorted(n for n, lvl in stored.node_level.items() if lvl == level)


def _reach(
    stored: StoredTree, node: int, target: int, kept: frozenset[int]
) -> list[int]:
    """The agent children ``node`` stands for when the next kept level is
    ``target``: itself if it is there, or below it on a kept level (a jumped
    edge); otherwise whatever it leads to."""
    level = stored.node_level[node]
    if level == target or (level < target and level in kept):
        return [node]
    lower = target if level > target else max(k for k in kept if k < level)
    return [
        found
        for child in stored.children.get(node, ())
        for found in _reach(stored, child, lower, kept)
    ]


def _reachable(tree: ExportTree) -> list[int]:
    seen: list[int] = []
    stack = [tree.root]
    while stack:
        node_id = stack.pop()
        seen.append(node_id)
        stack.extend(reversed(tree.nodes[node_id].children))
    return seen
