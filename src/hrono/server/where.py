"""What a topic is ABOUT, taken from the files it holds (#198).

A brief-derived name is only as good as the model that wrote one. On a tree
summarised by a weak model every topic is called "This group covers State,
what…", and twenty-six identical labels are not a map. The files underneath do
not lie: a topic whose chunks are all under ``src/hrono/db`` is the database,
whatever its brief says.

So each topic is labelled by the deepest directory that holds MOST of its
chunks — not the strict common prefix, which collapses to ``src/hrono`` for
half a repository and distinguishes nothing. A topic whose chunks genuinely
straddle the tree is named by the two roots it straddles instead.
"""

from __future__ import annotations

import sqlite3
from collections import Counter

# How much of a topic a directory must hold to name it. Below this the topic
# really is spread, and claiming one directory would be a label that lies.
SHARE = 0.6


def by_node(conn: sqlite3.Connection, tree: str) -> dict[int, str]:
    """Every topic in the tree, labelled by where its chunks live.

    An upper topic has no chunks of its own, so it takes its descendants' —
    which is what makes the top of the map read as ``src + tests`` rather than
    as nothing at all.
    """
    held = _member_dirs(conn, tree)
    children = _children(conn, tree)
    for node in _bottom_up(conn, tree):
        for child in children.get(node, ()):
            held.setdefault(node, []).extend(held.get(child, ()))
    return {node: _label(dirs) for node, dirs in held.items()}


def _member_dirs(
    conn: sqlite3.Connection, tree: str
) -> dict[int, list[tuple[str, ...]]]:
    """Each leaf topic's chunks, as the directories that contain them."""
    held: dict[int, list[tuple[str, ...]]] = {}
    for row in conn.execute(
        "SELECT m.node_id AS node_id, s.path AS path "
        "FROM node_members m "
        "JOIN sections s ON s.id = m.section_id "
        "JOIN nodes n ON n.id = m.node_id "
        "WHERE n.tree = ?",
        (tree,),
    ).fetchall():
        held.setdefault(int(row["node_id"]), []).append(
            tuple(str(row["path"]).split("/")[:-1])
        )
    return held


def _children(conn: sqlite3.Connection, tree: str) -> dict[int, list[int]]:
    edges: dict[int, list[int]] = {}
    for row in conn.execute(
        "SELECT c.parent_id AS parent, c.child_id AS child "
        "FROM node_children c JOIN nodes n ON n.id = c.parent_id "
        "WHERE n.tree = ?",
        (tree,),
    ).fetchall():
        edges.setdefault(int(row["parent"]), []).append(int(row["child"]))
    return edges


def _bottom_up(conn: sqlite3.Connection, tree: str) -> list[int]:
    """Topics from the leaves upwards, so a parent is reached after its kids.

    Level is the tree's own depth counter — 0 at the leaves — so ordering by
    it is the topological order without walking the edges twice.
    """
    return [
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ? ORDER BY level, id",
            (tree,),
        ).fetchall()
    ]


def _label(dirs: list[tuple[str, ...]]) -> str:
    deepest = _dominant(dirs)
    if deepest:
        return "/".join(deepest)
    return _straddled(dirs)


def _dominant(dirs: list[tuple[str, ...]]) -> tuple[str, ...]:
    """Descend while one directory still holds SHARE of everything."""
    total = len(dirs)
    prefix: tuple[str, ...] = ()
    while True:
        depth = len(prefix)
        deeper = Counter(
            path[: depth + 1]
            for path in dirs
            if len(path) > depth and path[:depth] == prefix
        )
        if not deeper:
            return prefix
        candidate, held = deeper.most_common(1)[0]
        if held < total * SHARE:
            return prefix
        prefix = candidate


def _straddled(dirs: list[tuple[str, ...]]) -> str:
    """No directory holds it: name the two roots it is spread across."""
    roots = Counter(path[0] if path else "/" for path in dirs)
    return " + ".join(name for name, _ in roots.most_common(2))
