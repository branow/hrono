"""Load the stored tree for a named tree into the pure ``StoredTree`` shape.

Reads the nodes at every level, the node->child-node edges (#060 node_children),
and each leaf node's sections (#040 node_members) for one tree, and picks the
single highest-level node as the root. The collapse (#078) and render (#079)
operate on this pure data; the endpoint (#080) loads it here.
"""

from __future__ import annotations

import sqlite3

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

    root = max(node_level, key=lambda nid: node_level[nid])
    return StoredTree(
        root=root,
        node_level=node_level,
        children={k: tuple(v) for k, v in children.items()},
        sections={k: tuple(v) for k, v in sections.items()},
    )
