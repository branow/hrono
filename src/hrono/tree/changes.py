"""What a run changed in the tree, measured before and after it.

A finished run should say what it did to the map — topics added and removed,
sections re-filed, briefs rewritten — and the ops' own counts answer a
different question (what each stage processed). So a composite op takes a
snapshot before its first stage and compares after its last: the difference
is the one thing every stage's counts together cannot tell you.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class Snapshot:
    topics: frozenset[int]
    filed: dict[int, int]  # section id -> the topic holding it
    briefs: dict[int, str]  # topic id -> when its brief was written


def snapshot(conn: sqlite3.Connection, tree: str) -> Snapshot:
    """The tree's topics, where each section is filed, and its briefs."""
    topics = frozenset(
        int(row[0])
        for row in conn.execute("SELECT id FROM nodes WHERE tree = ?", (tree,))
    )
    filed = {
        int(row[0]): int(row[1])
        for row in conn.execute(
            "SELECT m.section_id, m.node_id FROM node_members m "
            "JOIN nodes n ON n.id = m.node_id WHERE n.tree = ?",
            (tree,),
        )
    }
    written = {
        int(row[0]): str(row[1])
        for row in conn.execute(
            "SELECT b.node_id, b.created_at FROM briefs b "
            "JOIN nodes n ON n.id = b.node_id WHERE n.tree = ?",
            (tree,),
        )
    }
    return Snapshot(topics, filed, written)


def since(
    conn: sqlite3.Connection, tree: str, before: Snapshot
) -> dict[str, int]:
    """What moved between ``before`` and now, as counts."""
    after = snapshot(conn, tree)
    return {
        "topics_added": len(after.topics - before.topics),
        "topics_removed": len(before.topics - after.topics),
        "sections_refiled": sum(
            1
            for section, node in after.filed.items()
            if section in before.filed and before.filed[section] != node
        ),
        "briefs_rewritten": sum(
            1
            for node, when in after.briefs.items()
            if before.briefs.get(node) != when
        ),
    }
