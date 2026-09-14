"""The #086 pool invariant, as an assertion any lifecycle test can make.

`0017_incubator.sql`: "every chunk is in exactly one cluster OR pending here,
never both, never neither" — plus #095's time bound, that nothing stays pending
for more than ``MAX_AGE`` batches. Both halves are asserted per SECTION, the key
membership and (since `0022_pending_by_section.sql`) the pool share: two
sections with identical bodies at different paths are two chunks, and only one
of them may be homeless.

The time bound carries the precondition ``incubator._force_assign`` states —
only a PLACEABLE chunk is bound. A chunk with no combined vector, or a tree with
no level-0 cluster to fall back on, cannot be force-assigned anywhere, so ageing
is not a rescue that exists for it.

Brief sections (``node://``, #071) are not corpus chunks and are excluded; they
are never clustered.
"""

from __future__ import annotations

from hrono.cluster import incubator
from hrono.cluster.blend import combined_vector
from hrono.cluster.incubator import MAX_AGE
from hrono.cluster.store import node_centroids
from hrono.db.database import Database


def assert_pool_invariant(db: Database, tree: str, model: str) -> None:
    """Assert every corpus section is in exactly one node XOR pending."""
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
            (path, wait)
            for _, digest, path, wait in pool
            if centroids
            and combined_vector(conn, digest, path, model) is not None
        ]
        row = conn.execute(
            "SELECT batch FROM tree_batch WHERE tree = ?", (tree,)
        ).fetchone()
        batch = int(row["batch"]) if row is not None else 0

    parked = {section_id for section_id, _, _, _ in pool}
    for section in sections:
        homes = int(section["homes"])
        waiting = int(section["id"]) in parked
        assert homes <= 1, f"{section['path']} is in {homes} nodes"
        assert homes == 1 or waiting, f"{section['path']} is in no node"
        assert not (homes == 1 and waiting), (
            f"{section['path']} is clustered AND pending"
        )

    for path, wait in placeable:
        assert batch - wait <= MAX_AGE, f"{path} pending {batch - wait} batches"
