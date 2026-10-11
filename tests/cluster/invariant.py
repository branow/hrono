"""The pool invariant, as an assertion any lifecycle test can make.

`0017_incubator.sql`: "every chunk is in exactly one cluster OR pending here,
never both, never neither" — plus the incubator's run bound, that nothing
placeable is still pending once a run ends (the pool is drained and homed at
the end of every update and settle). Both halves are asserted per SECTION,
the key membership and (since `0022_pending_by_section.sql`) the pool share: two
sections with identical bodies at different paths are two chunks, and only one
of them may be homeless.

The run bound carries the precondition ``incubator._force_assign`` states —
only a PLACEABLE chunk is bound. A chunk with no combined vector, or a tree with
no level-0 cluster to fall back on, cannot be force-assigned anywhere, so
``incubator.home`` is not a rescue that exists for it. Call this only between
runs: inside one, a parked chunk legitimately waits for the run's pool pass.

Brief sections (``node://``) are not corpus chunks and are excluded; they
are never clustered.
"""

from __future__ import annotations

from hrono.cluster import incubator
from hrono.cluster.blend import combined_vector
from hrono.cluster.store import node_centroids
from hrono.db.database import Database


def assert_pool_invariant(db: Database, tree: str, model: str) -> None:
    """Assert each section is in one node XOR pending; none placeable waits."""
    with db.connect() as conn:
        sections = conn.execute(
            "SELECT s.id, s.path, "
            "(SELECT COUNT(*) FROM node_members m JOIN nodes n "
            " ON n.id = m.node_id "
            " WHERE m.section_id = s.id AND n.tree = ? AND n.level = 0) "
            "AS homes "
            "FROM sections s WHERE s.source_type <> 'node'",
            (tree,),
        ).fetchall()
        pool = incubator.pending(conn, tree)
        centroids = node_centroids(conn, tree, model)
        placeable = [
            path
            for _, digest, path, _ in pool
            if centroids
            and combined_vector(conn, digest, path, model) is not None
        ]

    parked = {section_id for section_id, _, _, _ in pool}
    for section in sections:
        homes = int(section["homes"])
        waiting = int(section["id"]) in parked
        assert homes <= 1, f"{section['path']} is in {homes} nodes"
        assert homes == 1 or waiting, f"{section['path']} is in no node"
        assert not (homes == 1 and waiting), (
            f"{section['path']} is clustered AND pending"
        )

    assert not placeable, f"placeable sections left pending: {placeable}"


def assert_every_leaf_is_reachable(db: Database, tree: str) -> None:
    """Assert no level-0 node is orphaned once the tree has a level above it.

    ``root.md``'s child listing is rendered from parent EDGES, so a leaf
    with no parent is written to the export and unreachable in it — an agent
    walking the map from the root never sees the topic. Vacuous while a
    tree is a single level: ``build_tree``'s ``_collect_root`` gives it a root
    before there is anything to be reachable from.
    """
    with db.connect() as conn:
        above = conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE tree = ? AND level > 0", (tree,)
        ).fetchone()[0]
        if not above:
            return
        orphans = [
            (int(row["id"]), row["path"])
            for row in conn.execute(
                "SELECT n.id AS id, "
                "(SELECT s.path FROM node_members m "
                " JOIN sections s ON s.id = m.section_id "
                " WHERE m.node_id = n.id LIMIT 1) AS path "
                "FROM nodes n WHERE n.tree = ? AND n.level = 0 "
                "AND n.id NOT IN (SELECT child_id FROM node_children)",
                (tree,),
            ).fetchall()
        ]
    assert not orphans, f"leaf nodes unreachable from the root: {orphans}"
