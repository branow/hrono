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
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from hrono.cluster import store
from hrono.cluster.blend import combined_vector
from hrono.cluster.recipe import MIN_POINTS

MAX_AGE = 5  # batches a chunk may wait while the pool stays below the minimum

CoreLabeler = Callable[[Sequence[Sequence[float]]], Sequence[int]]


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
    pool = pending(conn, tree)
    ready = [
        (chash, path, combined_vector(conn, chash, path, model_name))
        for chash, path, _ in pool
    ]
    ready = [(c, p, v) for c, p, v in ready if v is not None]
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
            store.add_leaf_node(conn, tree, members)

    for chash, path in grouped.get(-1, []):
        _force_assign(conn, tree, chash, path, model_name, centroids)
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

    Only runs while the pool is too small to drain — a full pool takes the drain
    path instead, so nothing waits forever either way.
    """
    if count(conn, tree) >= MIN_POINTS:
        return 0
    centroids = store.node_centroids(conn, tree, model_name)
    forced = 0
    for chash, path, batch in pending(conn, tree):
        if current_batch - batch > max_age and _force_assign(
            conn, tree, chash, path, model_name, centroids
        ):
            forced += 1
    return forced


def _force_assign(
    conn: sqlite3.Connection,
    tree: str,
    content_hash: str,
    path: str,
    model_name: str,
    centroids: dict[int, tuple[float, ...]],
) -> bool:
    vector = combined_vector(conn, content_hash, path, model_name)
    if vector is None or not centroids:
        return False
    node_id, similarity = max(
        ((nid, _dot(vector, c)) for nid, c in centroids.items()),
        key=lambda pair: pair[1],
    )
    for section_id in _section_ids(conn, content_hash):
        store.add_member(
            conn, node_id, section_id, forced=True, similarity=similarity
        )
    unpark(conn, tree, content_hash)
    return True


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
