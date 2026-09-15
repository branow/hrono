"""The incubator / pending pool (#086, T35): where sub-TAU chunks wait.

The incremental ``update`` (#085) parks a chunk that fits no existing cluster
here, BY SECTION — the same key membership uses, so the pool is exactly the
complement of the tree and identical bodies at different paths park
independently (#095). When the pool reaches what the clusterer can actually
reduce (``recipe.MIN_POINTS`` — a pool the mini-pipeline cannot reduce is not a
drainable pool) it DRAINS via the scoped mini-pipeline (UMAP -> HDBSCAN leaf
over the pool only, deterministic): only density-core clusters emit as new leaf
nodes; residual noise is force-assigned to the nearest EXISTING cluster ignoring
TAU (a chunk outside the tree is unfindable — worse than one alien member),
carrying a ``forced`` flag so the misfit monitor (T37) re-checks it. Aging
force-assigns a chunk that has waited too many batches while the pool stayed too
small. Constants are baked.

The pool is DRIVEN, not self-draining (#095): ``update`` ages then drains at the
end of every batch's placement, ``settle`` drains after its warm reconcile, and
a full rebuild (``cluster``) homes every section by construction, so ``sweep``
retires the pool rows it has just made obsolete. Together these keep the #086
invariant true: a chunk is in exactly one cluster OR pending, never both, never
neither — and never pending for more than ``MAX_AGE`` batches once it is
PLACEABLE (see ``_force_assign`` for that bound). Every drain and age outcome is
written to ``update_log`` in propagate's shape, so the pool has an auditable
history.

Lock discipline follows the ops (#035/#040): ``drain`` takes a ``Database``, not
a connection, because its mini-pipeline is real UMAP -> HDBSCAN — it reads the
pool under the read door, reduces it off the lock, and re-acquires to persist.
Everything else here is a handful of dot products and runs in its caller's
transaction.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from hrono.cluster import store
from hrono.cluster.blend import combined_vector
from hrono.cluster.recipe import MIN_POINTS
from hrono.db.database import Database
from hrono.db.update_log import record

# A "batch" is ONE `update` RUN over the tree, not one changed source in it
# (#099): the run allocates a single `tree_batch.batch` and every source it
# touches stamps parked chunks with that number, so the wait below is measured
# in runs. `park` keeps the batch a chunk was FIRST parked at
# (ON CONFLICT DO NOTHING, #095), and a chunk that joins a node is unparked, so
# the clock only ever runs while the chunk is genuinely homeless.
MAX_AGE = 5  # update runs a chunk may wait while the pool stays too small

CoreLabeler = Callable[[Sequence[Sequence[float]]], Sequence[int]]
Parked = tuple[int, str, str, int]  # section id, content hash, path, batch
Ready = tuple[tuple[int, str, str, tuple[float, ...]], ...]


def park(
    conn: sqlite3.Connection,
    tree: str,
    section_id: int,
    batch: int,
) -> None:
    """Park a chunk in the pending pool; a re-park keeps its original wait."""
    conn.execute(
        "INSERT INTO pending(tree, section_id, batch, created_at) "
        "VALUES (?, ?, ?, ?) ON CONFLICT(tree, section_id) DO NOTHING",
        (tree, section_id, batch, _now()),
    )


def pending(conn: sqlite3.Connection, tree: str) -> tuple[Parked, ...]:
    """Return the pool as (section, hash, path, batch), oldest batch first."""
    rows = conn.execute(
        "SELECT p.section_id, s.content_hash, s.path, p.batch FROM pending p "
        "JOIN sections s ON s.id = p.section_id WHERE p.tree = ? "
        "ORDER BY p.batch, p.section_id",
        (tree,),
    ).fetchall()
    return tuple(
        (
            int(row["section_id"]),
            row["content_hash"],
            row["path"],
            int(row["batch"]),
        )
        for row in rows
    )


def parked_batch(
    conn: sqlite3.Connection, tree: str, section_id: int
) -> int | None:
    """The batch a section was parked at, or None if it is not pending."""
    row = conn.execute(
        "SELECT batch FROM pending WHERE tree = ? AND section_id = ?",
        (tree, section_id),
    ).fetchone()
    return None if row is None else int(row["batch"])


def unpark(conn: sqlite3.Connection, tree: str, section_id: int) -> None:
    conn.execute(
        "DELETE FROM pending WHERE tree = ? AND section_id = ?",
        (tree, section_id),
    )


def count(conn: sqlite3.Connection, tree: str) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM pending WHERE tree = ?", (tree,)
        ).fetchone()[0]
    )


def drain(
    database: Database,
    tree: str,
    model_name: str,
    *,
    core_labeler: CoreLabeler | None = None,
) -> bool:
    """If the pool is full enough, drain it; return whether a drain ran."""
    with database.connect() as conn:
        ready = _ready(conn, tree, model_name)
    if len(ready) < MIN_POINTS:
        return False

    labeler = core_labeler if core_labeler is not None else _default_core
    labels = labeler([vector for *_, vector in ready])

    grouped: dict[int, list[tuple[int, str, str]]] = defaultdict(list)
    for (section_id, chash, path, _), label in zip(ready, labels, strict=True):
        grouped[int(label)].append((section_id, chash, path))

    with database.write() as conn:
        # residual noise attaches to a pre-existing cluster, so snapshot
        # centroids BEFORE the new cores are added.
        centroids = store.node_centroids(conn, tree, model_name)
        for label, group in grouped.items():
            if label < 0:
                continue
            for section_id, _chash, _path in group:
                unpark(conn, tree, section_id)
            node_id = store.add_leaf_node(
                conn,
                tree,
                [(section_id, False, None) for section_id, _, _ in group],
            )
            record(conn, tree, node_id, "drain", "core")

        for section_id, chash, path in grouped.get(-1, []):
            node_id = _force_assign(
                conn, tree, section_id, chash, path, model_name, centroids
            )
            if node_id is not None:
                record(conn, tree, node_id, "drain", "forced")
    return True


def age(
    conn: sqlite3.Connection,
    tree: str,
    model_name: str,
    current_batch: int,
    *,
    max_age: int = MAX_AGE,
) -> int:
    """Force-assign chunks pending longer than ``max_age`` batches; count them.

    Only runs while the pool cannot drain — a drainable pool takes the drain
    path instead, which re-homes every chunk anyway. The gate is the DRAINABLE
    size (#094's ``MIN_POINTS``, counted over chunks that actually have a
    vector), not the raw row count, so a pool the mini-pipeline can never reduce
    still ages out instead of waiting forever.
    """
    if len(_ready(conn, tree, model_name)) >= MIN_POINTS:
        return 0
    centroids = store.node_centroids(conn, tree, model_name)
    forced = 0
    for section_id, chash, path, batch in pending(conn, tree):
        if current_batch - batch <= max_age:
            continue
        node_id = _force_assign(
            conn, tree, section_id, chash, path, model_name, centroids
        )
        if node_id is not None:
            record(conn, tree, node_id, "age", "forced")
            forced += 1
    return forced


def sweep(conn: sqlite3.Connection, tree: str) -> int:
    """Retire pool rows for sections a full rebuild has already homed.

    ``cluster`` re-clusters every embedded section, so after a rebuild a parked
    chunk is a member again while its pool row still claims it is homeless —
    "in a cluster AND pending", the other half of the #086 invariant. Retires
    per SECTION, so a twin the rebuild could not see keeps its row. Returns how
    many rows were retired.
    """
    cursor = conn.execute(
        "DELETE FROM pending WHERE tree = ? AND section_id IN ("
        "SELECT m.section_id FROM node_members m "
        "JOIN nodes n ON n.id = m.node_id "
        "WHERE n.tree = ? AND n.level = 0)",
        (tree, tree),
    )
    return int(cursor.rowcount)


def _ready(conn: sqlite3.Connection, tree: str, model_name: str) -> Ready:
    """The pool restricted to chunks whose combined vector is available."""
    vectors = (
        (
            section_id,
            chash,
            path,
            combined_vector(conn, chash, path, model_name),
        )
        for section_id, chash, path, _ in pending(conn, tree)
    )
    return tuple((s, c, p, v) for s, c, p, v in vectors if v is not None)


def _force_assign(
    conn: sqlite3.Connection,
    tree: str,
    section_id: int,
    content_hash: str,
    path: str,
    model_name: str,
    centroids: dict[int, tuple[float, ...]],
) -> int | None:
    """Attach a chunk to its nearest cluster ignoring TAU; return that node.

    Returns None when the chunk is UNPLACEABLE — no combined vector (its model
    never embedded it) or no existing cluster to fall back on (a tree with no
    level-0 node, #112) — and leaves it parked, since forcing it somewhere is
    not an option that exists. That is the standing bound on "nothing waits
    forever": ageing rescues every chunk the tree can actually accept.
    """
    vector = combined_vector(conn, content_hash, path, model_name)
    if vector is None or not centroids:
        return None
    node_id, similarity = max(
        ((nid, _dot(vector, c)) for nid, c in centroids.items()),
        key=lambda pair: pair[1],
    )
    store.add_member(
        conn, node_id, section_id, forced=True, similarity=similarity
    )
    unpark(conn, tree, section_id)
    return node_id


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _default_core(vectors: Sequence[Sequence[float]]) -> Sequence[int]:
    from hrono.cluster.build import core_labels

    return core_labels(vectors)


def _now() -> str:
    return datetime.now(UTC).isoformat()
