"""Local cluster repairs: split, migrate, dissolve.

The one-cluster repairs the misfit monitor triggers — each touches ONLY
its cluster's members and lets only that cluster's brief regenerate (via brief
freshness). All three reuse settled primitives: the scoped mini-pipeline (the
incubator's ``core_labels``), the placement rule (``assign_or_park``), and the
store's centroid maths. New nodes carry the content-hash signature so a
later full rebuild matches them.

- ``split``  — a cluster over MAX_CAP (the summarization budget) re-clusters its
  own members into density-core children; residual noise attaches to the nearest
  child. The oversized node retires.
- a PINNED member is never moved by any of these: a hand-placed chunk
  that migrates on the next batch is the silent revert pins exist to prevent.
- ``migrate`` — a cluster over the misfit threshold sheds its misfit members
  (best_other > own), each moving to the cluster that actually fits it. A
  cluster holding a FORCED member runs the rule whatever its rate: one alien
  pioneer rarely moves a rate past 0.25, and leaving it married to the topic for
  ever is the defect 0017 promised not to have. Moving it re-records the
  member unforced, so the flag keeps meaning "not yet revisited".
- ``dissolve`` — a cluster below two members retires; each survivor re-enters
  the placement rule against the remaining clusters.
- upper levels get the migrate rule too, in brief space over child edges:
  a child attached by proximity below TAU is the level >= 1 twin of a
  forced member, and without this it would stay under the wrong parent for
  ever —
  polluting that parent's brief, because a parent's brief is written over its
  children.

The ``repair`` op picks the repair per cluster from its size and stored misfit
rate. Constants baked (MAX_CAP 30, min_cluster_size 5, misfit threshold 0.25).
"""

from __future__ import annotations

import math
import sqlite3
from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence

from hrono import pins
from hrono.cluster import monitor, placement, store
from hrono.cluster.blend import combined_vector
from hrono.cluster.levels import migrate_children
from hrono.embed.model import resolve_embedding_model
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.registry.collections.trees import DEFAULT_TREE

MAX_CAP = 30  # summarization budget: a cluster larger than this splits
MISFIT_THRESHOLD = 0.25  # per-cluster misfit fraction that triggers a migrate

_Member = tuple[int, str, str]  # section_id, content_hash, path
CoreLabeler = Callable[[Sequence[Sequence[float]]], Sequence[int]]


def repair(
    job: Job,
    context: JobContext,
    *,
    core_labeler: CoreLabeler | None = None,
) -> Mapping[str, object]:
    """Apply the fitting local repair to each cluster from its size + misfit."""
    tree = job.tree or DEFAULT_TREE
    done = {"dissolved": 0, "split": 0, "migrated": 0, "freed": 0}
    with context.database.write() as conn:
        # what a pin HELD is part of this run's outcome
        held = pins.pinned(conn, pins.MEMBERSHIP)
        done["pinned"] = len(held)
        model = str(resolve_embedding_model(conn, job.scope)["name"])
        batch = _batch(conn, tree)
        # every LEAF, not every centroid: a node whose members all lack a
        # vector has no centroid, so iterating `node_centroids` made an
        # emptied leaf invisible to the one repair (dissolve) it needs.
        for node_id in _leaves(conn, tree):
            size = store.member_count(conn, node_id)
            forced = len(store.forced_members(conn, node_id))
            if size < 2:
                if _holds_pin(conn, node_id, held):
                    continue  # a human holds a member here
                done["dissolved"] += int(
                    dissolve(conn, tree, node_id, model, batch)
                )
            elif size > MAX_CAP:
                done["split"] += len(
                    split(conn, tree, node_id, model, core_labeler=core_labeler)
                )
            elif _needs_migrate(conn, tree, node_id):
                moved = migrate(conn, tree, node_id, model)
                done["migrated"] += moved
                # a forced member that MOVED is a pioneer freed: the
                # decision an operator most wants to see the system revisit.
                done["freed"] += min(moved, forced)
        done["reparented"] = _repair_upper_levels(conn, tree, model)
        done["removed"] = _drop_childless(conn, tree)
    return done


def _leaves(conn: sqlite3.Connection, tree: str) -> tuple[int, ...]:
    rows = conn.execute(
        "SELECT id FROM nodes WHERE tree = ? AND level = 0 ORDER BY id",
        (tree,),
    ).fetchall()
    return tuple(int(row["id"]) for row in rows)


def _holds_pin(
    conn: sqlite3.Connection, node_id: int, held: frozenset[int]
) -> bool:
    return any(
        section_id in held
        for section_id, _, _ in store.node_member_rows(conn, node_id)
    )


def _drop_childless(conn: sqlite3.Connection, tree: str) -> int:
    """Delete upper nodes with no children left; return how many went.

    A parent can lose every child — a dissolve, a split's retirement, a
    migrate that empties it — and nothing removed it: ``brief_upper`` skips a
    node with no child briefs, so its OLD brief kept being served by export
    and recall, describing children that no longer exist. Bottom-up, because
    deleting a childless level-1 node can leave its level-2 parent childless
    in the same pass. The sole top node is exempt: a one-node tree's root is
    legitimately childless.
    """
    removed = 0
    for level in _upper_levels(conn, tree):
        for row in conn.execute(
            "SELECT id FROM nodes n WHERE n.tree = ? AND n.level = ? "
            "AND NOT EXISTS (SELECT 1 FROM node_children c "
            "WHERE c.parent_id = n.id) ORDER BY n.id",
            (tree, level),
        ).fetchall():
            if _sole_node(conn, tree, int(row["id"])):
                continue
            store.delete_node(conn, int(row["id"]))
            removed += 1
    return removed


def _sole_node(conn: sqlite3.Connection, tree: str, node_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM nodes WHERE tree = ? AND id != ? LIMIT 1",
        (tree, node_id),
    ).fetchone()
    return row is None


def _repair_upper_levels(
    conn: sqlite3.Connection, tree: str, model_name: str
) -> int:
    """Re-parent misfit children at every level above the leaf.

    A level runs the rule when its stored rate is over the threshold OR any of
    its parents holds a child attached by proximity — the same either/or
    `_needs_migrate` applies at level 0, and for the same reason: one poorly
    attached child rarely moves a parent's rate past 0.25, and attach places a
    child under the NEAREST parent, so the rate can never see it.
    """
    moved = 0
    for level in _upper_levels(conn, tree):
        parents = [
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM nodes WHERE tree = ? AND level = ? ORDER BY id",
                (tree, level),
            ).fetchall()
        ]
        if any(
            monitor.cluster_rate(conn, tree, p) > MISFIT_THRESHOLD
            or store.attached_children(conn, p)
            for p in parents
        ):
            moved += migrate_children(conn, tree, level, model_name)
    return moved


def _upper_levels(conn: sqlite3.Connection, tree: str) -> tuple[int, ...]:
    rows = conn.execute(
        "SELECT DISTINCT level FROM nodes WHERE tree = ? AND level > 0 "
        "ORDER BY level",
        (tree,),
    ).fetchall()
    return tuple(int(row["level"]) for row in rows)


def _needs_migrate(conn: sqlite3.Connection, tree: str, node_id: int) -> bool:
    """Over the misfit threshold, or holding a member forced past TAU."""
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
    over: int = MAX_CAP,
) -> tuple[int, ...]:
    """Split an over-``over`` cluster into density-core children (new ids).

    ``over`` is the size that makes a split WANTED, and it is MAX_CAP for the
    automatic repair because that is the summarization budget. A human asking
    for a split is not subject to that budget — a six-member topic they can see
    is really two is exactly the case a manual split exists for — so they pass
    their own floor. What does not change is the refusal below: fewer than two
    density cores is not a split, whoever asked.
    """
    rows = store.node_member_rows(conn, node_id)
    if len(rows) <= over:
        return ()
    members = _vectors(conn, node_id, model_name)
    # a member with no vector cannot be judged, but dropping it breaks the
    # one-home invariant (in exactly one cluster or pending): it is dealt into
    # the biggest child below, with the topic's company, instead of into
    # nothing.
    vectored = {member[0] for member, _ in members}
    unjudged = [row for row in rows if row[0] not in vectored]
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

    anchored = pins.anchors(conn, pins.MEMBERSHIP)
    # WHERE THE SPLIT TOPIC HUNG, read before it is deleted. A split made two
    # new leaves and retired the old one without ever attaching them, so the
    # halves of a topic that was under the root became unparented nodes beside
    # the tree — two circles on the map with no line to anything, and a root
    # whose brief no longer mentions a seventh of the corpus. The
    # divided topic is still in the same place; it is only narrower.
    above = store.parent_of(conn, node_id)
    new_ids: list[int] = []
    biggest: int | None = None
    for group in sorted(positive.values(), key=len, reverse=True):
        child = store.add_leaf_node(
            conn, tree, [(member[0], False, None) for member, _ in group]
        )
        if biggest is None:
            biggest = child
        if above is not None:
            store.add_child(conn, above, child, attached=False, similarity=None)
        for member, _vector in group:
            if anchored.get(member[0]) == node_id:
                # the topic was divided, not lost: the child holding this
                # chunk IS what the operator pointed at, narrowed.
                pins.reanchor(conn, pins.MEMBERSHIP, member[0], child)
        new_ids.append(child)
    for section_id, _, _ in unjudged:
        store.add_member(
            conn,
            _require_child(biggest),
            section_id,
            forced=True,
            similarity=None,
        )
        if anchored.get(section_id) == node_id:
            pins.reanchor(
                conn, pins.MEMBERSHIP, section_id, _require_child(biggest)
            )
    store.delete_node(conn, node_id)  # its brief cascades
    return tuple(new_ids)


def _require_child(child: int | None) -> int:
    if child is None:  # unreachable: a split only proceeds with >= 2 cores
        raise ValueError("split produced no children")
    return child


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
    held = pins.pinned(conn, pins.MEMBERSHIP)
    moves: list[tuple[int, int, float]] = []
    for section_id, content_hash, path in store.node_member_rows(conn, node_id):
        if section_id in held:
            continue  # a human put it here
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
    """Retire a below-two cluster; re-place survivors via the rule."""
    if store.member_count(conn, node_id) >= 2:
        return False
    retire(conn, tree, node_id, model_name, batch, centroids)
    return True


def retire(
    conn: sqlite3.Connection,
    tree: str,
    node_id: int,
    model_name: str,
    batch: int,
    centroids: dict[int, tuple[float, ...]] | None = None,
) -> dict[str, int]:
    """Retire a node and re-place every member; report where they landed.

    The operation ``dissolve`` performs once its BELOW-TWO rule says it may.
    They are separate because the rule is the automatic repair's, not the
    operation's: an operator dissolving a topic they can see is wrong is not
    asking about its size, and a `dissolve` bound by the rule would report
    success over a node it had silently left standing.

    The counts are the honest answer to "what happened to my chunks": a member
    whose best topic scores below TAU is PARKED, not placed, and an operator
    told only "6 members replaced" would never learn that.
    """
    centroids = centroids or store.node_centroids(conn, tree, model_name)
    others = {nid: c for nid, c in centroids.items() if nid != node_id}
    survivors = store.node_member_rows(conn, node_id)
    store.delete_node(conn, node_id)
    outcomes = dict.fromkeys(("joined", "parked", "skipped"), 0)
    for section_id, content_hash, path in survivors:
        outcomes[
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
        ] += 1
    return outcomes


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
