"""The #086 pool invariant, as an assertion any lifecycle test can make.

`0017_incubator.sql`: "every chunk is in exactly one cluster OR pending here,
never both, never neither" — plus #095's time bound, that nothing stays pending
for more than ``MAX_AGE`` batches. Brief sections (``node://``, #071) are not
corpus chunks and are excluded; they are never clustered.
"""

from __future__ import annotations

from hrono.cluster.incubator import MAX_AGE
from hrono.db.database import Database


def assert_pool_invariant(db: Database, tree: str) -> None:
    """Assert every corpus section is in exactly one node XOR pending."""
    with db.connect() as conn:
        sections = conn.execute(
            "SELECT s.id, s.path, s.content_hash, "
            "(SELECT COUNT(*) FROM node_members m JOIN nodes n "
            " ON n.id = m.node_id "
            " WHERE m.section_id = s.id AND n.tree = ? AND n.level = 0) "
            "AS homes "
            "FROM sections s WHERE s.source_type <> 'node'",
            (tree,),
        ).fetchall()
        parked = {
            row["content_hash"]: int(row["batch"])
            for row in conn.execute(
                "SELECT content_hash, batch FROM pending WHERE tree = ?",
                (tree,),
            ).fetchall()
        }
        row = conn.execute(
            "SELECT batch FROM tree_batch WHERE tree = ?", (tree,)
        ).fetchone()
        batch = int(row["batch"]) if row is not None else 0

    for section in sections:
        homes = int(section["homes"])
        waiting = section["content_hash"] in parked
        assert homes <= 1, f"{section['path']} is in {homes} nodes"
        assert homes == 1 or waiting, f"{section['path']} is in no node"
        assert not (homes == 1 and waiting), (
            f"{section['path']} is clustered AND pending"
        )

    for content_hash, wait_batch in parked.items():
        assert batch - wait_batch <= MAX_AGE, (
            f"{content_hash} pending {batch - wait_batch} batches"
        )
