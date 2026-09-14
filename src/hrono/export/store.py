"""Load the stored tree for a named tree into the pure ``StoredTree`` shape.

Reads the nodes at every level, the node->child-node edges (#060 node_children),
and each leaf node's sections (#040 node_members) for one tree, and picks the
single highest-level node as the root. The collapse (#078) and render (#079)
operate on this pure data; the endpoint (#080) loads it here.

``build_tree``'s ``_collect_root`` guarantees exactly ONE node at the top level
whenever the recursion stops, so a forest is never a legitimate stored tree — it
only appears when a build died half-way. Loading one is therefore a defect that
fails loudly (#096, F20): picking one of them arbitrarily served a single
topic's brief as ``root.md`` and silently dropped the other briefs from the
export.
"""

from __future__ import annotations

import sqlite3

from hrono.errors import Internal
from hrono.export.collapse import StoredTree


def load(conn: sqlite3.Connection, tree: str) -> StoredTree | None:
    """Return the stored tree for ``tree``, or None if it has no nodes."""
    node_level = {
        int(row["id"]): int(row["level"])
        for row in conn.execute(
            "SELECT id, level FROM nodes WHERE tree = ?", (tree,)
        ).fetchall()
    }
    if not node_level:
        return None

    children: dict[int, list[int]] = {}
    for row in conn.execute(
        "SELECT c.parent_id AS parent, c.child_id AS child "
        "FROM node_children c "
        "JOIN nodes n ON n.id = c.parent_id WHERE n.tree = ? "
        "ORDER BY c.parent_id, c.child_id",
        (tree,),
    ).fetchall():
        children.setdefault(int(row["parent"]), []).append(int(row["child"]))

    sections: dict[int, list[int]] = {}
    for row in conn.execute(
        "SELECT m.node_id AS node, m.section_id AS section FROM node_members m "
        "JOIN nodes n ON n.id = m.node_id WHERE n.tree = ? "
        "ORDER BY m.node_id, m.section_id",
        (tree,),
    ).fetchall():
        sections.setdefault(int(row["node"]), []).append(int(row["section"]))

    root = _root(tree, node_level)
    return StoredTree(
        root=root,
        node_level=node_level,
        children={k: tuple(v) for k, v in children.items()},
        sections={k: tuple(v) for k, v in sections.items()},
    )


def _root(tree: str, node_level: dict[int, int]) -> int:
    """The single node at the top level; a forest there is a DEFECT (#096)."""
    top = max(node_level.values())
    roots = sorted(nid for nid, level in node_level.items() if level == top)
    if len(roots) != 1:
        raise Internal(
            f"tree is not built to a single root: {len(roots)} nodes at its "
            f"top level",
            details={"tree": tree, "level": top, "nodes": roots},
        )
    return roots[0]
