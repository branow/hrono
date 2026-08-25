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

import hashlib
import sqlite3
from array import array
from collections import defaultdict
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from hrono.cluster.blend import combined_vector


def section_combined_vectors(
    conn: sqlite3.Connection, model_name: str
) -> tuple[tuple[int, tuple[float, ...]], ...]:
    """Return (section_id, combined vector) for every embedded section."""
    rows = conn.execute(
        "SELECT id, path, content_hash FROM sections "
        "WHERE source_type != 'node' ORDER BY id"
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
    """Rebuild a leaf tree level, PRESERVING node ids for unchanged clusters.

    ``members`` is (label, section_id, attached, assignment_similarity). Each
    label's signature is the set of its members' CONTENT HASHES (stable across a
    re-split's new section ids), so a cluster whose content is unchanged reuses
    its existing node id — keeping its brief (#068). ``coords`` is (section_id,
    reduced vector).
    """
    now = _now()
    by_label: dict[int, list[tuple[int, bool, float | None]]] = defaultdict(
        list
    )
    for label, section_id, attached, similarity in members:
        by_label[label].append((section_id, attached, similarity))

    hashes = _section_hashes(conn, [sid for _, sid, _, _ in members])
    label_sig = {
        label: _signature(hashes[sid] for sid, _, _ in rows)
        for label, rows in by_label.items()
    }
    node_id_of = _reconcile(conn, tree, level, label_sig, now)

    for label, rows in by_label.items():
        node_id = node_id_of[label]
        for section_id, attached, similarity in rows:
            conn.execute(
                "INSERT INTO node_members(node_id, section_id, attached, "
                "assignment_similarity, created_at) VALUES (?, ?, ?, ?, ?)",
                (node_id, section_id, int(attached), similarity, now),
            )

    conn.execute("DELETE FROM section_coords WHERE tree = ?", (tree,))
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
    """Rebuild an UPPER tree level, PRESERVING node ids for unchanged clusters.

    ``members`` is (label, child_node_id, attached, assignment_similarity). Each
    label's signature is the set of its child NODE IDs (stable once the level
    below is), so an unchanged grouping reuses its node id and keeps its brief;
    a child that changed id (its content changed) shifts its parent's signature,
    minting a new parent — so a change propagates only up its own path (#068).
    """
    now = _now()
    by_label: dict[int, list[tuple[int, bool, float | None]]] = defaultdict(
        list
    )
    for label, child_id, attached, similarity in members:
        by_label[label].append((child_id, attached, similarity))

    label_sig = {
        label: _signature(f"n{cid}" for cid, _, _ in rows)
        for label, rows in by_label.items()
    }
    node_id_of = _reconcile(conn, tree, level, label_sig, now)

    for label, rows in by_label.items():
        parent_id = node_id_of[label]
        for child_id, attached, similarity in rows:
            conn.execute(
                "INSERT INTO node_children(parent_id, child_id, attached, "
                "assignment_similarity, created_at) VALUES (?, ?, ?, ?, ?)",
                (parent_id, child_id, int(attached), similarity, now),
            )


def _reconcile(
    conn: sqlite3.Connection,
    tree: str,
    level: int,
    label_sig: dict[int, str],
    now: str,
) -> dict[int, int]:
    """Map each label to a node id, reusing an existing node on signature match.

    A label whose signature matches an existing node at this level keeps that
    node id (and its brief, un-cascaded, with its members/children cleared for
    refresh); an unmatched label mints a new node; any existing node not reused
    is retired (its brief cascades).
    """
    existing: dict[str, int] = {}
    for row in conn.execute(
        "SELECT id, signature FROM nodes WHERE tree = ? AND level = ? "
        "ORDER BY id",
        (tree, level),
    ).fetchall():
        if row["signature"] is not None:
            existing.setdefault(row["signature"], int(row["id"]))

    node_id_of: dict[int, int] = {}
    kept: set[int] = set()
    for label in sorted(label_sig):
        signature = label_sig[label]
        reuse = existing.get(signature)
        if reuse is not None and reuse not in kept:
            node_id = reuse
            conn.execute(
                "UPDATE nodes SET label = ? WHERE id = ?", (label, node_id)
            )
            conn.execute(
                "DELETE FROM node_members WHERE node_id = ?", (node_id,)
            )
            conn.execute(
                "DELETE FROM node_children WHERE parent_id = ?", (node_id,)
            )
        else:
            cursor = conn.execute(
                "INSERT INTO nodes(tree, level, label, signature, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (tree, level, label, signature, now),
            )
            node_id = int(cursor.lastrowid or 0)
        node_id_of[label] = node_id
        kept.add(node_id)

    for row in conn.execute(
        "SELECT id FROM nodes WHERE tree = ? AND level = ?", (tree, level)
    ).fetchall():
        if int(row["id"]) not in kept:
            conn.execute("DELETE FROM nodes WHERE id = ?", (int(row["id"]),))
    return node_id_of


def _section_hashes(
    conn: sqlite3.Connection, section_ids: Sequence[int]
) -> dict[int, str]:
    hashes: dict[int, str] = {}
    for section_id in set(section_ids):
        row = conn.execute(
            "SELECT content_hash FROM sections WHERE id = ?", (section_id,)
        ).fetchone()
        if row is not None:
            hashes[section_id] = row["content_hash"]
    return hashes


def _signature(tokens: Iterable[object]) -> str:
    joined = ",".join(sorted(str(token) for token in tokens))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(UTC).isoformat()
