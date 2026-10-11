"""The incubator / pending pool: a TEMPORARY holding area inside one run.

The incremental ``update`` parks a chunk that fits no existing cluster (below
``TAU``) here, BY SECTION — the same key membership uses, so identical bodies
at different paths park independently. The pool never outlives the run that
filled it. At the end of the run it is emptied, as the research did it
(``research.ipynb`` steps 21–23):

- **Drain**: when the pool holds what the clusterer can reduce
  (``recipe.MIN_POINTS``), the scoped mini-pipeline (UMAP -> HDBSCAN leaf over
  the pool only, deterministic) emits its density-core clusters as new leaf
  nodes. A genuinely new area forms its own topics instead of polluting old
  ones.
- **Home**: everything still in the pool — drain noise, or a pool too small to
  cluster — is force-assigned to the nearest EXISTING cluster, ignoring
  ``TAU``. It carries a ``forced`` flag, so the misfit monitor re-checks it
  first and moves it once its real siblings form a topic. Forced is what makes
  a placement provisional; leaving a chunk outside the tree is not, because a
  chunk outside the tree is unfindable.

``update`` and ``settle`` drain then home; a full rebuild (``cluster``) homes
every section by construction, and ``sweep`` retires the rows it made
obsolete. So a chunk is in exactly one cluster, and in the pool only while the
run that parked it is still running — unless it is UNPLACEABLE (no vector, or
a tree with no cluster at all; see ``_force_assign``). Every drain and home
outcome is written to ``update_log`` in propagate's shape.

Lock discipline follows the ops: ``drain`` takes a ``Database``, not
a connection, because its mini-pipeline is real UMAP -> HDBSCAN — it reads the
pool under the read door, reduces it off the lock, and re-acquires to persist.
Everything else here is a handful of dot products and runs in its caller's
transaction.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime

from hrono.cluster import store
from hrono.cluster.blend import combined_vector
from hrono.cluster.recipe import MIN_POINTS
from hrono.db.database import Database
from hrono.db.update_log import record

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
        still = _still_pending(conn, tree, grouped)
        for label, group in grouped.items():
            if label < 0:
                continue
            members = [s for s, _, _ in group if s in still]
            if not members:
                continue
            for section_id in members:
                unpark(conn, tree, section_id)
            node_id = store.add_leaf_node(
                conn,
                tree,
                [(section_id, False, None) for section_id in members],
            )
            record(conn, tree, node_id, "drain", "core")

        for section_id, chash, path in grouped.get(-1, []):
            if section_id not in still:
                continue
            node_id = _force_assign(
                conn, tree, section_id, chash, path, model_name, centroids
            )
            if node_id is not None:
                record(conn, tree, node_id, "drain", "forced")
    return True


def _still_pending(
    conn: sqlite3.Connection,
    tree: str,
    grouped: Mapping[int, Sequence[tuple[int, str, str]]],
) -> frozenset[int]:
    """Of the sections this drain computed over, which are STILL parked.

    The pool is read under the read door and the clustering runs off the lock,
    so the write block is acting on a SNAPSHOT. Trusting it writes a second
    level-0 membership for any section that found a home in between — the "is in
    2 nodes" half of the one-home invariant, in a tree nobody has touched since.

    Unreachable while one process owns the database and the worker runs one job
    at a time, which is why this is a re-check rather than a lock: it costs one
    query, changes nothing about the shape every heavy op uses (read under the
    door, reduce off the lock, re-acquire to persist), and makes the persist
    depend on the state it is persisting into rather than on a promise.
    """
    ids = [section for group in grouped.values() for section, _, _ in group]
    if not ids:
        return frozenset()
    marks = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT section_id FROM pending WHERE tree = ? "  # noqa: S608
        f"AND section_id IN ({marks})",
        (tree, *ids),
    ).fetchall()
    return frozenset(int(row["section_id"]) for row in rows)


def home(conn: sqlite3.Connection, tree: str, model_name: str) -> int:
    """Force-assign every placeable chunk still in the pool; count them.

    The end of every run's pool pass, after any drain: what the drain did not
    turn into a new topic joins the nearest existing one, flagged ``forced``.
    """
    centroids = store.node_centroids(conn, tree, model_name)
    forced = 0
    for section_id, chash, path, _batch in pending(conn, tree):
        node_id = _force_assign(
            conn, tree, section_id, chash, path, model_name, centroids
        )
        if node_id is not None:
            record(conn, tree, node_id, "home", "forced")
            forced += 1
    return forced


def sweep(conn: sqlite3.Connection, tree: str) -> int:
    """Retire pool rows for sections a full rebuild has already homed.

    ``cluster`` re-clusters every embedded section, so after a rebuild a parked
    chunk is a member again while its pool row still claims it is homeless — "in
    a cluster AND pending", the other half of the one-home invariant. Retires
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
    level-0 node) — and leaves it parked, since forcing it somewhere is
    not an option that exists: ``home`` places every chunk the tree can
    actually accept.
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
