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
import math
import sqlite3
from array import array
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
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


def backfill_coords(
    conn: sqlite3.Connection, tree: str, model_name: str
) -> int:
    """Give every level-0 member a reduced coordinate; return how many written.

    Warm init (T39.2) needs a coordinate for EVERY section in the build, and
    only a full build produces real UMAP coordinates — incremental placement
    (#085) decides by dot product and produces none. So one `update` was enough
    to break coverage, `stored_coords` correctly returned None, and settle cold
    -inits for ever: the warm path could never fire in practice (#101, F28).

    A placed section has no coordinate of its own, so it inherits its cluster's:
    the mean of the members that do have one, which keeps it inside the layout
    it joined. A cluster where NOBODY has one — a drained pool, say — takes the
    reduced centroid of the nearest cluster that does, which is the same
    approximation one level out. With no coordinates anywhere there is no layout
    to preserve, so nothing is written and the caller inits fresh.
    """
    covered: dict[int, tuple[float, ...]] = {}
    for row in conn.execute(
        "SELECT section_id, coords FROM section_coords WHERE tree = ?", (tree,)
    ).fetchall():
        values = array("f")
        values.frombytes(row["coords"])
        covered[int(row["section_id"])] = tuple(values)

    members: dict[int, list[int]] = {}
    for row in conn.execute(
        "SELECT m.node_id AS n, m.section_id AS s FROM node_members m "
        "JOIN nodes ON nodes.id = m.node_id "
        "WHERE nodes.tree = ? AND nodes.level = 0 ORDER BY m.section_id",
        (tree,),
    ).fetchall():
        members.setdefault(int(row["n"]), []).append(int(row["s"]))
    missing = {
        node_id: [s for s in sections if s not in covered]
        for node_id, sections in members.items()
    }
    if not any(missing.values()):
        return 0

    anchors = {
        node_id: _mean([covered[s] for s in sections if s in covered])
        for node_id, sections in members.items()
        if any(s in covered for s in sections)
    }
    if not anchors:
        return 0
    centroids = node_centroids(conn, tree, model_name)
    now = _now()
    written = 0
    for node_id, sections in missing.items():
        coord = anchors.get(node_id) or _nearest_anchor(
            node_id, centroids, anchors
        )
        if coord is None:
            continue
        for section_id in sections:
            _write_coord(conn, tree, section_id, coord, now)
            written += 1
    return written


def _nearest_anchor(
    node_id: int,
    centroids: dict[int, tuple[float, ...]],
    anchors: dict[int, tuple[float, ...]],
) -> tuple[float, ...] | None:
    """The reduced centroid of the nearest cluster that has one."""
    own = centroids.get(node_id)
    if own is None:
        return None
    candidates = [
        (sum(a * b for a, b in zip(own, centroids[other], strict=True)), other)
        for other in anchors
        if other in centroids and other != node_id
    ]
    if not candidates:
        return None
    return anchors[max(candidates)[1]]


def _mean(coords: Sequence[tuple[float, ...]]) -> tuple[float, ...]:
    dims = len(coords[0])
    return tuple(sum(c[i] for c in coords) / len(coords) for i in range(dims))


def _write_coord(
    conn: sqlite3.Connection,
    tree: str,
    section_id: int,
    coord: Sequence[float],
    now: str,
) -> None:
    conn.execute(
        "INSERT INTO section_coords(tree, section_id, dims, coords, "
        "created_at) VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(tree, section_id) DO UPDATE SET dims = excluded.dims, "
        "coords = excluded.coords, created_at = excluded.created_at",
        (tree, section_id, len(coord), array("f", coord).tobytes(), now),
    )


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


def add_child(
    conn: sqlite3.Connection,
    parent_id: int,
    child_id: int,
    *,
    attached: bool,
    similarity: float | None,
) -> None:
    """Attach one existing node to a parent one level up (#114).

    The late-arrival counterpart of ``add_member``: a leaf the incubator emits
    after ``build_tree`` has recursed has no parent, and ``root.md``'s child
    listing is rendered from parent EDGES, so an agent walking the map from the
    root never reaches it. Refreshes the parent's signature over its child ids
    — the same value ``replace_level`` writes — so #068 still matches the parent
    to itself at the next rebuild, and #064 sees the parent's brief as stale.
    """
    conn.execute(
        "INSERT INTO node_children(parent_id, child_id, attached, "
        "assignment_similarity, created_at) VALUES (?, ?, ?, ?, ?)",
        (parent_id, child_id, int(attached), similarity, _now()),
    )
    conn.execute(
        "UPDATE nodes SET signature = ? WHERE id = ?",
        (node_child_signature(conn, parent_id), parent_id),
    )


def node_child_signature(conn: sqlite3.Connection, node_id: int) -> str:
    """The signature of an upper node's current child node ids."""
    rows = conn.execute(
        "SELECT child_id FROM node_children WHERE parent_id = ? "
        "ORDER BY child_id",
        (node_id,),
    ).fetchall()
    return _signature(f"n{int(row['child_id'])}" for row in rows)


def unparented(
    conn: sqlite3.Connection, tree: str, level: int = 0
) -> tuple[int, ...]:
    """Nodes at ``level`` with no parent edge — unreachable from the root."""
    return tuple(
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ? AND level = ? AND id NOT IN "
            "(SELECT child_id FROM node_children) ORDER BY id",
            (tree, level),
        ).fetchall()
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


def add_leaf_node(
    conn: sqlite3.Connection,
    tree: str,
    members: Sequence[tuple[int, bool, float | None]],
) -> int:
    """Add ONE new level-0 node (incremental #086), return its id.

    ``members`` is (section_id, forced, assignment_similarity). Its signature is
    set from the members' content hashes so a later full rebuild can match it.
    """
    now = _now()
    cursor = conn.execute(
        "INSERT INTO nodes(tree, level, label, created_at) "
        "VALUES (?, 0, -1, ?)",
        (tree, now),
    )
    node_id = int(cursor.lastrowid or 0)
    for section_id, forced, similarity in members:
        _insert_member(conn, node_id, section_id, forced, similarity, now)
    conn.execute(
        "UPDATE nodes SET signature = ? WHERE id = ?",
        (node_content_signature(conn, node_id), node_id),
    )
    return node_id


def add_member(
    conn: sqlite3.Connection,
    node_id: int,
    section_id: int,
    *,
    forced: bool,
    similarity: float | None,
) -> None:
    """Add one section to an existing node (force-assign #086); refresh sig."""
    _insert_member(conn, node_id, section_id, forced, similarity, _now())
    conn.execute(
        "UPDATE nodes SET signature = ? WHERE id = ?",
        (node_content_signature(conn, node_id), node_id),
    )


def _insert_member(
    conn: sqlite3.Connection,
    node_id: int,
    section_id: int,
    forced: bool,
    similarity: float | None,
    now: str,
) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO node_members(node_id, section_id, attached, "
        "assignment_similarity, forced, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (node_id, section_id, int(forced), similarity, int(forced), now),
    )


def node_content_signature(conn: sqlite3.Connection, node_id: int) -> str:
    """The content-hash signature of a node's current section members."""
    rows = conn.execute(
        "SELECT s.content_hash AS h FROM node_members m "
        "JOIN sections s ON s.id = m.section_id WHERE m.node_id = ? "
        "ORDER BY s.content_hash",
        (node_id,),
    ).fetchall()
    return _signature(row["h"] for row in rows)


def node_centroids(
    conn: sqlite3.Connection, tree: str, model_name: str
) -> dict[int, tuple[float, ...]]:
    """Return each leaf node's unit centroid (mean of member vectors)."""
    centroids: dict[int, tuple[float, ...]] = {}
    for row in conn.execute(
        "SELECT id FROM nodes WHERE tree = ? AND level = 0", (tree,)
    ).fetchall():
        node_id = int(row["id"])
        vectors = []
        for member in conn.execute(
            "SELECT s.content_hash AS h, s.path AS p FROM node_members m "
            "JOIN sections s ON s.id = m.section_id WHERE m.node_id = ?",
            (node_id,),
        ).fetchall():
            vector = combined_vector(conn, member["h"], member["p"], model_name)
            if vector is not None:
                vectors.append(vector)
        if vectors:
            centroids[node_id] = _renormalized_mean(vectors)
    return centroids


@dataclass(frozen=True)
class Membership:
    """A section's place in a leaf node: the node and how it got there."""

    node_id: int
    similarity: float | None
    forced: bool


def membership(
    conn: sqlite3.Connection, tree: str, section_id: int
) -> Membership | None:
    """Return the section's level-0 membership in ``tree``, or None.

    Carries the assignment as it was recorded, so a rename can re-attach the
    replacement section on exactly the terms the original had (#100).
    """
    row = conn.execute(
        "SELECT m.node_id AS n, m.assignment_similarity AS sim, "
        "m.forced AS forced FROM node_members m "
        "JOIN nodes ON nodes.id = m.node_id "
        "WHERE nodes.tree = ? AND nodes.level = 0 AND m.section_id = ?",
        (tree, section_id),
    ).fetchone()
    if row is None:
        return None
    sim = row["sim"]
    return Membership(
        node_id=int(row["n"]),
        similarity=None if sim is None else float(sim),
        forced=bool(row["forced"]),
    )


def section_node(
    conn: sqlite3.Connection, tree: str, section_id: int
) -> int | None:
    """Return the level-0 node a section belongs to in ``tree``, or None."""
    row = conn.execute(
        "SELECT m.node_id AS n FROM node_members m "
        "JOIN nodes ON nodes.id = m.node_id "
        "WHERE nodes.tree = ? AND nodes.level = 0 AND m.section_id = ?",
        (tree, section_id),
    ).fetchone()
    return int(row["n"]) if row is not None else None


def member_count(conn: sqlite3.Connection, node_id: int) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM node_members WHERE node_id = ?", (node_id,)
        ).fetchone()[0]
    )


def forced_members(conn: sqlite3.Connection, node_id: int) -> frozenset[int]:
    """Section ids force-assigned into this node ignoring TAU (#086 T35.3)."""
    rows = conn.execute(
        "SELECT section_id FROM node_members WHERE node_id = ? AND forced = 1",
        (node_id,),
    ).fetchall()
    return frozenset(int(row["section_id"]) for row in rows)


def forced_holders(conn: sqlite3.Connection, tree: str) -> frozenset[int]:
    """Level-0 node ids holding at least one force-assigned member."""
    rows = conn.execute(
        "SELECT DISTINCT m.node_id AS n FROM node_members m "
        "JOIN nodes ON nodes.id = m.node_id "
        "WHERE nodes.tree = ? AND nodes.level = 0 AND m.forced = 1",
        (tree,),
    ).fetchall()
    return frozenset(int(row["n"]) for row in rows)


def node_member_rows(
    conn: sqlite3.Connection, node_id: int
) -> tuple[tuple[int, str, str], ...]:
    """Return (section_id, content_hash, path) for a node's members."""
    rows = conn.execute(
        "SELECT s.id AS id, s.content_hash AS h, s.path AS p "
        "FROM node_members m JOIN sections s ON s.id = m.section_id "
        "WHERE m.node_id = ? ORDER BY s.id",
        (node_id,),
    ).fetchall()
    return tuple((int(r["id"]), r["h"], r["p"]) for r in rows)


def remove_member(
    conn: sqlite3.Connection, node_id: int, section_id: int
) -> None:
    """Drop a section from a node and refresh the node's content signature."""
    conn.execute(
        "DELETE FROM node_members WHERE node_id = ? AND section_id = ?",
        (node_id, section_id),
    )
    conn.execute(
        "UPDATE nodes SET signature = ? WHERE id = ?",
        (node_content_signature(conn, node_id), node_id),
    )


def delete_node(conn: sqlite3.Connection, node_id: int) -> None:
    """Remove a node (members, children, brief cascade)."""
    conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))


def _renormalized_mean(vectors: Sequence[Sequence[float]]) -> tuple[float, ...]:
    dims = len(vectors[0])
    mean = [sum(v[i] for v in vectors) / len(vectors) for i in range(dims)]
    norm = math.sqrt(sum(x * x for x in mean))
    if norm == 0.0:
        return tuple(mean)
    return tuple(x / norm for x in mean)


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
