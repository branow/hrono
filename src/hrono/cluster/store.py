"""Load the vectors a cluster build needs and persist its result.

Reading: ``section_combined_vectors`` walks every stored section and blends its
content and path vectors (#039) into the combined clustering vector, skipping
sections whose components are not embedded yet. ``stored_coords`` returns the
prior reduced coordinates for a warm-init rebuild, or None when any is missing.

Writing: ``replace_tree`` rebuilds a tree's level from scratch — it clears the
level's nodes (members cascade) and coords, then inserts one node per cluster
label with its members and each section's reduced coordinate. Kept free of the
numeric libraries so persistence stays importable without the ``cluster`` extra.
"""

from __future__ import annotations

import sqlite3
from array import array
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime

from hrono.cluster.blend import combined_vector


def section_combined_vectors(
    conn: sqlite3.Connection, model_name: str
) -> tuple[tuple[int, tuple[float, ...]], ...]:
    """Return (section_id, combined vector) for every embedded section."""
    rows = conn.execute(
        "SELECT id, path, content_hash FROM sections ORDER BY id"
    ).fetchall()
    pairs: list[tuple[int, tuple[float, ...]]] = []
    for row in rows:
        combined = combined_vector(
            conn, row["content_hash"], row["path"], model_name
        )
        if combined is not None:
            pairs.append((int(row["id"]), combined))
    return tuple(pairs)


def stored_coords(
    conn: sqlite3.Connection, tree: str, section_ids: Sequence[int]
) -> tuple[tuple[float, ...], ...] | None:
    """Return prior reduced coords aligned to ``section_ids``, or None.

    Warm-init needs a coordinate for every section in the build; a partial set
    (a first build, or new sections since the last one) yields None so the
    caller inits fresh.
    """
    by_section: dict[int, tuple[float, ...]] = {}
    for row in conn.execute(
        "SELECT section_id, coords FROM section_coords WHERE tree = ?", (tree,)
    ).fetchall():
        values = array("f")
        values.frombytes(row["coords"])
        by_section[int(row["section_id"])] = tuple(values)
    if any(section_id not in by_section for section_id in section_ids):
        return None
    return tuple(by_section[section_id] for section_id in section_ids)


def replace_tree(
    conn: sqlite3.Connection,
    tree: str,
    level: int,
    members: Sequence[tuple[int, int, bool, float | None]],
    coords: Sequence[tuple[int, Sequence[float]]],
) -> None:
    """Rebuild a tree level: clear it, then insert nodes, members, and coords.

    ``members`` is (label, section_id, attached, assignment_similarity); each
    distinct label becomes one node. ``coords`` is (section_id, reduced vector).
    """
    now = _now()
    conn.execute(
        "DELETE FROM nodes WHERE tree = ? AND level = ?", (tree, level)
    )
    conn.execute("DELETE FROM section_coords WHERE tree = ?", (tree,))

    by_label: dict[int, list[tuple[int, bool, float | None]]] = defaultdict(
        list
    )
    for label, section_id, attached, similarity in members:
        by_label[label].append((section_id, attached, similarity))

    for label in sorted(by_label):
        cursor = conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, ?, ?, ?)",
            (tree, level, label, now),
        )
        node_id = int(cursor.lastrowid or 0)
        for section_id, attached, similarity in by_label[label]:
            conn.execute(
                "INSERT INTO node_members(node_id, section_id, attached, "
                "assignment_similarity, created_at) VALUES (?, ?, ?, ?, ?)",
                (node_id, section_id, int(attached), similarity, now),
            )

    for section_id, coord in coords:
        blob = array("f", coord).tobytes()
        conn.execute(
            "INSERT INTO section_coords(tree, section_id, dims, coords, "
            "created_at) VALUES (?, ?, ?, ?, ?)",
            (tree, section_id, len(coord), blob, now),
        )


def replace_level(
    conn: sqlite3.Connection,
    tree: str,
    level: int,
    members: Sequence[tuple[int, int, bool, float | None]],
) -> None:
    """Rebuild an UPPER tree level from child nodes: clear it, then insert.

    ``members`` is (label, child_node_id, attached, assignment_similarity); each
    distinct label becomes one node at ``level`` whose children (the level
    below) are linked in node_children. Unlike ``replace_tree`` (leaf sections)
    this carries no per-member coords — warm-init for upper levels is future.
    """
    now = _now()
    conn.execute(
        "DELETE FROM nodes WHERE tree = ? AND level = ?", (tree, level)
    )

    by_label: dict[int, list[tuple[int, bool, float | None]]] = defaultdict(
        list
    )
    for label, child_id, attached, similarity in members:
        by_label[label].append((child_id, attached, similarity))

    for label in sorted(by_label):
        cursor = conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES (?, ?, ?, ?)",
            (tree, level, label, now),
        )
        parent_id = int(cursor.lastrowid or 0)
        for child_id, attached, similarity in by_label[label]:
            conn.execute(
                "INSERT INTO node_children(parent_id, child_id, attached, "
                "assignment_similarity, created_at) VALUES (?, ?, ?, ?, ?)",
                (parent_id, child_id, int(attached), similarity, now),
            )


def _now() -> str:
    return datetime.now(UTC).isoformat()
