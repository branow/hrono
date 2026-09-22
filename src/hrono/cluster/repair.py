"""Local cluster repairs (#090, T38): split, migrate, dissolve.

The one-cluster repairs the misfit monitor (#089) triggers — each touches ONLY
its cluster's members and lets only that cluster's brief regenerate (via #064).
All three reuse settled primitives: the scoped mini-pipeline (#086's
``core_labels``), the placement rule (#085's ``assign_or_park``), and the
store's centroid maths. New nodes carry the #068 content-hash signature so a
later full rebuild matches them.

- ``split``  — a cluster over MAX_CAP (the summarization budget) re-clusters its
  own members into density-core children; residual noise attaches to the nearest
  child. The oversized node retires.
- ``migrate`` — a cluster over the misfit threshold sheds its misfit members
  (best_other > own), each moving to the cluster that actually fits it. A
  cluster holding a FORCED member runs the rule whatever its rate: one alien
  pioneer rarely moves a rate past 0.25, and leaving it married to the topic for
  ever is the defect 0017 promised not to have (#113). Moving it re-records the
  member unforced, so the flag keeps meaning "not yet revisited".
- ``dissolve`` — a cluster below two members retires; each survivor re-enters
  the placement rule against the remaining clusters.

The ``repair`` op picks the repair per cluster from its size and stored misfit
rate. Constants baked (MAX_CAP 30, min_cluster_size 5, misfit threshold 0.25).
"""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from collections.abc import Callable, Sequence

from hrono.cluster import monitor, placement, store
from hrono.cluster.blend import combined_vector
from hrono.embed.model import resolve_embedding_model
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext

MAX_CAP = 30  # summarization budget: a cluster larger than this splits
MISFIT_THRESHOLD = 0.25  # per-cluster misfit fraction that triggers a migrate

_Member = tuple[int, str, str]  # section_id, content_hash, path
CoreLabeler = Callable[[Sequence[Sequence[float]]], Sequence[int]]


def repair(
    job: Job,
    context: JobContext,
    *,
    core_labeler: CoreLabeler | None = None,
) -> None:
    """Apply the fitting local repair to each cluster from its size + misfit."""
    tree = job.tree or "default"
    with context.database.write() as conn:
        model = str(resolve_embedding_model(conn, job.scope)["name"])
        batch = _batch(conn, tree)
        for node_id in sorted(store.node_centroids(conn, tree, model)):
            size = store.member_count(conn, node_id)
            if size < 2:
                dissolve(conn, tree, node_id, model, batch)
            elif size > MAX_CAP:
                split(conn, tree, node_id, model, core_labeler=core_labeler)
            elif _needs_migrate(conn, tree, node_id):
                migrate(conn, tree, node_id, model)


def _needs_migrate(conn: sqlite3.Connection, tree: str, node_id: int) -> bool:
    """Over the misfit threshold, or holding a member forced past TAU (#113)."""
    if monitor.cluster_rate(conn, tree, node_id) > MISFIT_THRESHOLD:
        return True
    return bool(store.forced_members(conn, node_id))


def split(
    conn: sqlite3.Connection,
    tree: str,
    node_id: int,
    model_name: str,
    *,
    core_labeler: CoreLabeler | None = None,
) -> tuple[int, ...]:
    """Split an over-MAX_CAP cluster into density-core children (new ids)."""
    members = _vectors(conn, node_id, model_name)
    if len(members) <= MAX_CAP:
        return ()
    labeler = core_labeler if core_labeler is not None else _default_core
    labels = labeler([vector for _, vector in members])
    cores: dict[int, list[tuple[_Member, tuple[float, ...]]]] = defaultdict(
        list
    )
    for (member, vector), label in zip(members, labels, strict=True):
        cores[int(label)].append((member, vector))

    positive = {label: group for label, group in cores.items() if label >= 0}
    if len(positive) < 2:
        return ()  # not a genuine split; leave the cluster intact

    centroids = {
        label: _renormalized_mean([vector for _, vector in group])
        for label, group in positive.items()
    }
    for member, vector in cores.get(-1, []):
        best = max(positive, key=lambda label: _dot(vector, centroids[label]))
        positive[best].append((member, vector))

    new_ids = [
        store.add_leaf_node(
            conn, tree, [(member[0], False, None) for member, _ in group]
        )
        for group in positive.values()
    ]
    store.delete_node(conn, node_id)  # its brief cascades (#068)
    return tuple(new_ids)


def migrate(
    conn: sqlite3.Connection,
    tree: str,
    node_id: int,
    model_name: str,
    centroids: dict[int, tuple[float, ...]] | None = None,
) -> int:
    """Move this cluster's misfit chunks to a cluster that fits them better."""
    centroids = centroids or store.node_centroids(conn, tree, model_name)
    own = centroids.get(node_id)
    others = {nid: c for nid, c in centroids.items() if nid != node_id}
    moves: list[tuple[int, int, float]] = []
    for section_id, content_hash, path in store.node_member_rows(conn, node_id):
        vector = combined_vector(conn, content_hash, path, model_name)
        if vector is None or not others:
            continue
        target_id, best = max(
            ((nid, _dot(vector, c)) for nid, c in others.items()),
            key=lambda pair: pair[1],
        )
        own_sim = _dot(vector, own) if own else -1.0
        if best > own_sim:  # a misfit — some other cluster fits it better
            moves.append((section_id, target_id, best))
    for section_id, target_id, similarity in moves:
        store.remove_member(conn, node_id, section_id)
        store.add_member(
            conn, target_id, section_id, forced=False, similarity=similarity
        )
    return len(moves)


def dissolve(
    conn: sqlite3.Connection,
    tree: str,
    node_id: int,
    model_name: str,
    batch: int,
    centroids: dict[int, tuple[float, ...]] | None = None,
) -> bool:
    """Retire a below-two cluster; re-place survivors via the rule (#085)."""
    if store.member_count(conn, node_id) >= 2:
        return False
    centroids = centroids or store.node_centroids(conn, tree, model_name)
    others = {nid: c for nid, c in centroids.items() if nid != node_id}
    survivors = store.node_member_rows(conn, node_id)
    store.delete_node(conn, node_id)
    for section_id, content_hash, path in survivors:
        placement.assign_or_park(
            conn,
            tree,
            section_id=section_id,
            content_hash=content_hash,
            path=path,
            centroids=others,
            model_name=model_name,
            batch=batch,
        )
    return True


def _vectors(
    conn: sqlite3.Connection, node_id: int, model_name: str
) -> list[tuple[_Member, tuple[float, ...]]]:
    out: list[tuple[_Member, tuple[float, ...]]] = []
    for section_id, content_hash, path in store.node_member_rows(conn, node_id):
        vector = combined_vector(conn, content_hash, path, model_name)
        if vector is not None:
            out.append(((section_id, content_hash, path), vector))
    return out


def _default_core(vectors: Sequence[Sequence[float]]) -> Sequence[int]:
    from hrono.cluster.build import core_labels

    return core_labels(vectors)


def _renormalized_mean(vectors: Sequence[Sequence[float]]) -> tuple[float, ...]:
    dims = len(vectors[0])
    mean = [sum(v[i] for v in vectors) / len(vectors) for i in range(dims)]
    norm = math.sqrt(sum(x * x for x in mean))
    if norm == 0.0:
        return tuple(mean)
    return tuple(x / norm for x in mean)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _batch(conn: sqlite3.Connection, tree: str) -> int:
    row = conn.execute(
        "SELECT batch FROM tree_batch WHERE tree = ?", (tree,)
    ).fetchone()
    return int(row["batch"]) if row is not None else 0


OPS["repair"] = repair
