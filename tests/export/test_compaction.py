"""Compaction trades depth for width and says what it got."""

import time

import pytest

from hrono.export.collapse import (
    WIDTH,
    ExportTree,
    StoredTree,
    collapse,
    shape,
)

DEPTH = 25


def deep_tree() -> StoredTree:
    """25 stored levels; it branches in two every sixth level, and one level-12
    topic also holds a level-0 leaf directly (an edge that jumps 11 levels)."""
    node_level: dict[int, int] = {}
    children: dict[int, list[int]] = {}
    sections: dict[int, list[int]] = {}
    ids = iter(range(1, 10_000))

    def build(level: int) -> int:
        nid = next(ids)
        node_level[nid] = level
        if level == 0:
            sections[nid] = [nid * 10, nid * 10 + 1]
            return nid
        fan = 2 if level % 6 == 0 else 1
        children[nid] = [build(level - 1) for _ in range(fan)]
        if level == 12:
            jumped = next(ids)
            node_level[jumped] = 0
            sections[jumped] = [jumped * 10]
            children[nid].append(jumped)
        return nid

    root = build(DEPTH - 1)
    return StoredTree(root, node_level, children, sections)


def hops_to_each_section(tree: ExportTree) -> dict[int, int]:
    """Walk from the root as an agent does: one hop per page opened."""
    found: dict[int, int] = {}
    stack = [(tree.root, 1)]
    while stack:
        node_id, hops = stack.pop()
        node = tree.nodes[node_id]
        for section in node.sections:
            found[section] = hops
        stack.extend((child, hops + 1) for child in node.children)
    return found


def planted(stored: StoredTree) -> set[int]:
    return {s for found in stored.sections.values() for s in found}


@pytest.mark.parametrize("limit", [2, 3, 4])
def test_a_25_level_tree_exports_within_the_hop_limit(limit: int) -> None:
    stored = deep_tree()

    tree = collapse(stored, limit)
    hops = hops_to_each_section(tree)

    assert len({level for level in stored.node_level.values()}) == DEPTH
    assert tree.levels <= limit
    assert set(hops) == planted(stored)  # nothing dropped, the jump included
    assert max(hops.values()) <= limit


def wide_trap() -> StoredTree:
    """Even spacing keeps level 3 here, and level 3 is one topic over 300.

    6 root -> 5 -> 4 -> 3 (one node each) -> 15 at level 2 -> 300 at level 1
    (20 each) -> 300 leaves. Keeping level 3 puts all 300 on one page; keeping
    level 2 makes the widest index page 20.
    """
    node_level: dict[int, int] = {}
    children: dict[int, list[int]] = {}
    sections: dict[int, list[int]] = {}
    ids = iter(range(1, 10_000))

    def make(level: int) -> int:
        nid = next(ids)
        node_level[nid] = level
        return nid

    chain = [make(level) for level in (6, 5, 4, 3)]
    for upper, lower in zip(chain, chain[1:], strict=False):
        children[upper] = [lower]
    middles = [make(2) for _ in range(15)]
    children[chain[-1]] = middles
    for middle in middles:
        ones = [make(1) for _ in range(20)]
        children[middle] = ones
        for one in ones:
            leaf = make(0)
            children[one] = [leaf]
            sections[leaf] = [leaf * 10]
    return StoredTree(chain[0], node_level, children, sections)


def test_the_kept_levels_are_chosen_by_the_width_they_produce() -> None:
    stored = wide_trap()

    tree = collapse(stored, 3)
    measured = shape(tree)

    kept = {stored.node_level[n] for n in tree.nodes}
    assert kept == {6, 2, 0}  # not the evenly spaced {6, 3, 0}
    assert len(tree.nodes[tree.root].children) == 15
    assert measured.widest_page == 20
    assert measured.within_budget


def test_the_shape_reports_levels_pages_and_the_widest_page() -> None:
    tree = collapse(wide_trap(), 3)

    measured = shape(tree)

    assert measured.levels == 3
    assert measured.pages_per_level == (1, 15, 300)
    assert measured.width_budget == WIDTH


def test_a_page_over_budget_keeps_the_hop_limit_and_says_so() -> None:
    stored = wide_trap()

    tree = collapse(stored, 2)  # root and leaves only: 300 on the root page
    measured = shape(tree)

    assert tree.levels == 2
    assert measured.widest_page == 300
    assert measured.widest_node == stored.root
    assert not measured.within_budget


def test_a_tree_within_the_limit_is_the_stored_tree_itself() -> None:
    stored = wide_trap()

    tree = collapse(stored, 10)  # a limit above the depth pads nothing

    assert tree.levels == 7
    assert {n: tree.nodes[n].children for n in stored.children} == {
        n: tuple(c) for n, c in stored.children.items()
    }
    assert {n: tree.nodes[n].sections for n in stored.sections} == {
        n: tuple(s) for n, s in stored.sections.items()
    }


def test_the_same_tree_compacts_the_same_way_every_time() -> None:
    assert collapse(deep_tree(), 3) == collapse(deep_tree(), 3)
    assert collapse(wide_trap(), 4) == collapse(wide_trap(), 4)


def test_a_jumped_edge_counts_toward_the_width_it_lands_on() -> None:
    # root(3) -> A(2) holding 50 leaves directly, and B(2) -> two level-1
    # topics of one leaf each. Keeping level 1 looks narrow if the jump is not
    # counted, and puts all 52 on the root page; keeping level 2 tops out at A.
    node_level = {1: 3, 2: 2, 3: 2, 4: 1, 5: 1}
    children: dict[int, list[int]] = {1: [2, 3], 3: [4, 5]}
    sections: dict[int, list[int]] = {}
    for leaf in range(100, 150):
        node_level[leaf] = 0
        children.setdefault(2, []).append(leaf)
        sections[leaf] = [leaf * 10]
    for upper, leaf in ((4, 200), (5, 201)):
        node_level[leaf] = 0
        children[upper] = [leaf]
        sections[leaf] = [leaf * 10]

    measured = shape(collapse(StoredTree(1, node_level, children, sections), 3))

    assert measured.widest_page == 50
    assert measured.widest_node == 2


def broad_deep_tree() -> StoredTree:
    """26 levels, widening toward the leaves: 8,192 nodes, 2,048 leaves."""
    node_level: dict[int, int] = {}
    children: dict[int, list[int]] = {}
    sections: dict[int, list[int]] = {}
    ids = iter(range(1, 100_000))

    def build(level: int) -> int:
        nid = next(ids)
        node_level[nid] = level
        if level == 0:
            sections[nid] = [nid]
            return nid
        fan = 2 if level % 2 == 0 and level <= 22 else 1
        children[nid] = [build(level - 1) for _ in range(fan)]
        return nid

    return StoredTree(build(25), node_level, children, sections)


@pytest.mark.parametrize("limit", [4, 8, 12, 25])
def test_any_hop_limit_compacts_a_big_deep_tree_quickly(limit: int) -> None:
    # the choice is a shortest path, not every combination of kept levels
    # (~15 minutes at 12 hops on a 30-level tree). Measured on this
    # tree: 4 hops 0.10 s, 8 hops 0.32 s, 12 hops 0.11 s, 25 hops 0.09 s.
    stored = broad_deep_tree()

    started = time.perf_counter()
    tree = collapse(stored, limit)
    elapsed = time.perf_counter() - started

    assert len(stored.node_level) == 8192
    assert tree.levels == limit
    assert set(hops_to_each_section(tree)) == planted(stored)
    assert elapsed < 2.0


def test_a_page_of_exactly_the_budget_is_within_it() -> None:
    node_level = {1: 1}
    children = {1: list(range(100, 100 + WIDTH))}
    sections: dict[int, list[int]] = {}
    for leaf in children[1]:
        node_level[leaf] = 0
        sections[leaf] = [leaf]

    measured = shape(collapse(StoredTree(1, node_level, children, sections), 2))

    assert measured.widest_page == WIDTH
    assert measured.within_budget


def test_the_widest_page_is_minimised_before_the_total() -> None:
    # keeping level 2 makes two layers of 30; keeping level 1 makes 50 then 2.
    # Fewer entries in total (52 < 60), but one page of 50: the widest page is
    # what an agent pays for, so level 2 is kept.
    ids = iter(range(2, 10_000))
    node_level = {1: 3}
    children: dict[int, list[int]] = {1: []}
    sections: dict[int, list[int]] = {}

    def add(parent: int, level: int) -> int:
        nid = next(ids)
        node_level[nid] = level
        children.setdefault(parent, []).append(nid)
        if level == 0:
            sections[nid] = [nid]
        return nid

    for twos in [15] + [2] * 6 + [1] * 23:
        middle = add(1, 2)
        for _ in range(twos):
            one = add(middle, 1)
            for _ in range(2 if twos == 15 else 1):
                add(one, 0)

    tree = collapse(StoredTree(1, node_level, children, sections), 3)

    assert {node_level[n] for n in tree.nodes} == {3, 2, 0}
    assert shape(tree).widest_page == 30
