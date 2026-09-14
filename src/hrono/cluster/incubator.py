"""The incubator / pending pool (#086, T35): where sub-TAU chunks wait.

The incremental ``update`` (#085) parks a chunk that fits no existing cluster
here, by CONTENT HASH, instead of force-marrying it to strangers. When the pool
reaches what the clusterer can actually reduce (``recipe.MIN_POINTS`` — a pool
the mini-pipeline cannot reduce is not a drainable pool) it DRAINS via the
scoped mini-pipeline (UMAP -> HDBSCAN leaf over the pool only, deterministic):
only density-core clusters emit as new leaf nodes; residual noise is
force-assigned to the nearest EXISTING cluster ignoring TAU (a chunk outside the
tree is unfindable — worse than one alien member), carrying a ``forced`` flag so
the misfit monitor (T37) re-checks it. Aging force-assigns a chunk that has
waited too many batches while the pool stayed too small — nothing waits forever.
Constants are baked.

The pool is DRIVEN, not self-draining (#095): ``update`` ages then drains at the
end of every batch's placement, ``settle`` drains after its warm reconcile, and
a full rebuild (``cluster``) homes every section by construction, so ``sweep``
retires the pool rows it has just made obsolete. Together these keep the #086
invariant true: a chunk is in exactly one cluster OR pending, never both, never
neither — and never pending for more than ``MAX_AGE`` batches. Every drain and
age outcome is written to ``update_log`` in propagate's shape, so the pool has
an auditable history.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from hrono.cluster import store
from hrono.cluster.blend import combined_vector
from hrono.cluster.recipe import MIN_POINTS
from hrono.db.update_log import record

MAX_AGE = 5  # batches a chunk may wait while the pool stays below the minimum

CoreLabeler = Callable[[Sequence[Sequence[float]]], Sequence[int]]
Ready = tuple[tuple[str, str, tuple[float, ...]], ...]


def park(
    conn: sqlite3.Connection,
    tree: str,
    content_hash: str,
    path: str,
    batch: int,
) -> None:
    """Park a chunk in the pending pool (idempotent by content hash)."""
    conn.execute(
        "INSERT OR REPLACE INTO pending(tree, content_hash, path, batch, "
        "created_at) VALUES (?, ?, ?, ?, ?)",
        (tree, content_hash, path, batch, _now()),
    )


def pending(
    conn: sqlite3.Connection, tree: str
) -> tuple[tuple[str, str, int], ...]:
    """Return the pool as (content_hash, path, batch), oldest batch first."""
    rows = conn.execute(
        "SELECT content_hash, path, batch FROM pending WHERE tree = ? "
        "ORDER BY batch, content_hash",
        (tree,),
    ).fetchall()
    return tuple(
        (row["content_hash"], row["path"], int(row["batch"])) for row in rows
    )


def unpark(conn: sqlite3.Connection, tree: str, content_hash: str) -> None:
    conn.execute(
        "DELETE FROM pending WHERE tree = ? AND content_hash = ?",
        (tree, content_hash),
    )


def count(conn: sqlite3.Connection, tree: str) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM pending WHERE tree = ?", (tree,)
        ).fetchone()[0]
    )


def drain(
    conn: sqlite3.Connection,
    tree: str,
    model_name: str,
    *,
    core_labeler: CoreLabeler | None = None,
) -> bool:
    """If the pool is full enough, drain it; return whether a drain ran."""
    ready = _ready(conn, tree, model_name)
    if len(ready) < MIN_POINTS:
        return False

    labeler = core_labeler if core_labeler is not None else _default_core
    labels = labeler([v for _, _, v in ready])
    grouped: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for (chash, path, _), label in zip(ready, labels, strict=True):
        grouped[int(label)].append((chash, path))

    # residual noise attaches to a pre-existing cluster, so snapshot centroids
    # BEFORE the new cores are added.
    centroids = store.node_centroids(conn, tree, model_name)
    for label, group in grouped.items():
        if label < 0:
            continue
        members: list[tuple[int, bool, float | None]] = []
        for chash, _path in group:
            for section_id in _section_ids(conn, chash):
                members.append((section_id, False, None))
            unpark(conn, tree, chash)
        if members:
            node_id = store.add_leaf_node(conn, tree, members)
            record(conn, tree, node_id, "drain", "core")

    for chash, path in grouped.get(-1, []):
        node_id = _force_assign(conn, tree, chash, path, model_name, centroids)
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
    for chash, path, batch in pending(conn, tree):
        if current_batch - batch <= max_age:
            continue
        node_id = _force_assign(conn, tree, chash, path, model_name, centroids)
        if node_id is not None:
            record(conn, tree, node_id, "age", "forced")
            forced += 1
    return forced


def sweep(conn: sqlite3.Connection, tree: str) -> int:
    """Retire pool rows for chunks a full rebuild has already homed.

    ``cluster`` re-clusters every embedded section, so after a rebuild a parked
    chunk is a member again while its pool row still claims it is homeless —
    "in a cluster AND pending", the other half of the #086 invariant. Returns
    how many rows were retired.
    """
    cursor = conn.execute(
        "DELETE FROM pending WHERE tree = ? AND content_hash IN ("
        "SELECT s.content_hash FROM sections s "
        "JOIN node_members m ON m.section_id = s.id "
        "JOIN nodes n ON n.id = m.node_id "
        "WHERE n.tree = ? AND n.level = 0)",
        (tree, tree),
    )
    return int(cursor.rowcount)


def _ready(conn: sqlite3.Connection, tree: str, model_name: str) -> Ready:
    """The pool restricted to chunks whose combined vector is available."""
    vectors = (
        (chash, path, combined_vector(conn, chash, path, model_name))
        for chash, path, _ in pending(conn, tree)
    )
    return tuple((c, p, v) for c, p, v in vectors if v is not None)


def _force_assign(
    conn: sqlite3.Connection,
    tree: str,
    content_hash: str,
    path: str,
    model_name: str,
    centroids: dict[int, tuple[float, ...]],
) -> int | None:
    """Attach a chunk to its nearest cluster ignoring TAU; return that node."""
    vector = combined_vector(conn, content_hash, path, model_name)
    if vector is None or not centroids:
        return None
    node_id, similarity = max(
        ((nid, _dot(vector, c)) for nid, c in centroids.items()),
        key=lambda pair: pair[1],
    )
    for section_id in _section_ids(conn, content_hash):
        store.add_member(
            conn, node_id, section_id, forced=True, similarity=similarity
        )
    unpark(conn, tree, content_hash)
    return node_id


def _section_ids(conn: sqlite3.Connection, content_hash: str) -> list[int]:
    return [
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM sections WHERE content_hash = ?", (content_hash,)
        ).fetchall()
    ]


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _default_core(vectors: Sequence[Sequence[float]]) -> Sequence[int]:
    from hrono.cluster.build import core_labels

    return core_labels(vectors)


def _now() -> str:
    return datetime.now(UTC).isoformat()
