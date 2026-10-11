"""Collapse the stored tree to <= N agent-facing levels."""

from hrono.export.collapse import ExportTree, StoredTree, collapse


def balanced_tree() -> StoredTree:
    """A 4-level stored tree: root -> 2 -> 4 -> 8 leaves (2 sections each)."""
    node_level: dict[int, int] = {}
    children: dict[int, list[int]] = {}
    sections: dict[int, list[int]] = {}
    next_id = iter(range(1, 100))

    def build(level: int) -> int:
        nid = next(next_id)
        node_level[nid] = level
        if level == 0:
            sections[nid] = [nid * 1000, nid * 1000 + 1]
            return nid
        children[nid] = [build(level - 1) for _ in range(2)]
        return nid

    root = build(3)
    return StoredTree(
        root=root, node_level=node_level, children=children, sections=sections
    )


def _by_level(tree: ExportTree) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for node in tree.nodes.values():
        out.setdefault(node.level, []).append(node.node_id)
    return out


def _reachable_sections(tree: ExportTree) -> set[int]:
    return {s for node in tree.nodes.values() for s in node.sections}


def test_deep_tree_collapses_to_at_most_n_levels() -> None:
    tree = collapse(balanced_tree(), levels=3)
    assert tree.levels <= 3
    assert max(_by_level(tree)) == tree.levels - 1


def test_every_section_stays_reachable() -> None:
    stored = balanced_tree()
    tree = collapse(stored, levels=3)
    planted = {s for secs in stored.sections.values() for s in secs}
    assert _reachable_sections(tree) == planted  # 16 sections, all reachable


def test_branching_is_narrow_at_root_and_wider_toward_leaves() -> None:
    tree = collapse(balanced_tree(), levels=3)
    by_level = _by_level(tree)
    counts = [len(by_level[lvl]) for lvl in sorted(by_level)]
    assert counts[0] == 1  # single root
    assert counts == sorted(counts)  # non-decreasing width toward the leaves


def test_every_agent_node_is_backed_by_a_stored_node() -> None:
    stored = balanced_tree()
    tree = collapse(stored, levels=3)
    assert set(tree.nodes) <= set(stored.node_level)


def test_levels_below_two_is_clamped_not_a_crash() -> None:
    # the export endpoint takes levels as user input; levels 1 and 0 must not
    # raise ZeroDivisionError/IndexError — they clamp to the minimum useful 2
    # levels.
    for degenerate in (1, 0, -3):
        tree = collapse(balanced_tree(), levels=degenerate)
        assert tree.levels == 2  # root + leaves
        planted = {
            s for secs in balanced_tree().sections.values() for s in secs
        }
        assert _reachable_sections(tree) == planted


def test_leaf_agent_nodes_carry_sections_inner_do_not() -> None:
    tree = collapse(balanced_tree(), levels=3)
    leaf_level = tree.levels - 1
    for node in tree.nodes.values():
        if node.level == leaf_level:
            assert node.sections and not node.children
        else:
            assert node.children and not node.sections
