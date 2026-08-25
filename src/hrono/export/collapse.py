"""Collapse the deep stored tree to <= N agent-facing levels (T29).

Pure and deterministic (no LLM, no I/O): given the stored tree (each node's
level, the node->child-node edges, and each leaf node's sections) and a target
``levels`` N, keep N evenly-spaced stored levels — always including the root
level and stored level 0 (whose nodes carry the sections) — and re-parent across
the skipped levels so each kept node's agent children are its descendants at the
next kept level. Because deeper stored levels hold more nodes, the agent tree is
narrow at the root and widens toward the leaves by construction. A tree already
shallower than N is returned as-is (no padding).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass


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
    """Map the stored tree to an agent-facing tree of at most ``levels``."""
    present = sorted(set(stored.node_level.values()))
    kept = (
        present if len(present) <= levels else _evenly_spaced(present, levels)
    )
    kept_desc = sorted(kept, reverse=True)  # [root_level, ..., 0]
    agent_level = {level: i for i, level in enumerate(kept_desc)}
    leaf_level = kept_desc[-1]

    nodes: dict[int, ExportNode] = {}
    for stored_level in kept_desc:
        below = _next_lower(kept_desc, stored_level)
        for node in _at_level(stored, stored_level):
            if below is None:
                children: tuple[int, ...] = ()
                sections = tuple(stored.sections.get(node, ()))
            else:
                children = tuple(_descendants_at(stored, node, below))
                sections = ()
            nodes[node] = ExportNode(
                node_id=node,
                level=agent_level[stored_level],
                children=children,
                sections=sections if stored_level == leaf_level else (),
            )
    return ExportTree(root=stored.root, levels=len(kept_desc), nodes=nodes)


def _evenly_spaced(present: list[int], n: int) -> list[int]:
    last = len(present) - 1
    picks = sorted({round(i * last / (n - 1)) for i in range(n)})
    return [present[i] for i in picks]


def _next_lower(kept_desc: list[int], level: int) -> int | None:
    i = kept_desc.index(level)
    return kept_desc[i + 1] if i + 1 < len(kept_desc) else None


def _at_level(stored: StoredTree, level: int) -> list[int]:
    return sorted(n for n, lvl in stored.node_level.items() if lvl == level)


def _descendants_at(stored: StoredTree, node: int, target: int) -> list[int]:
    if stored.node_level[node] == target:
        return [node]
    out: list[int] = []
    for child in stored.children.get(node, ()):
        out.extend(_descendants_at(stored, child, target))
    return out
