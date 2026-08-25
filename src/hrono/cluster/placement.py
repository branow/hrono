"""The incremental placement rule (#085, T34): place only the changed chunks.

The differentiator's efficient form. Given the section-level deltas of a change
batch (from #083's diff, reconciled into the store) and a snapshot of the
PRE-BATCH cluster centroids, decide each changed chunk's cluster by a
deterministic dot product — never re-running UMAP/HDBSCAN, so untouched chunks
cannot move and churn equals changed content exactly:

- deleted -> its membership is already gone (reconcile cascade); the vacated
  cluster is dissolved if it drops below two members (each survivor re-placed).
- changed -> STICKY RE-CHECK vs its own PRE-BATCH centroid: >= TAU it stays put
  (only its brief goes stale via #064), else it re-enters the placement rule.
- moved -> same sticky re-check on the recomputed (new-path) combined vector;
  the content vector is reused (content-addressed, so embed skipped it).
- new -> placement rule: best similarity vs cluster CENTROIDS; >= TAU joins that
  cluster, otherwise it parks in the incubator (#086).

Constants are baked (TAU 0.70). Every decision is a dot product; a cluster whose
membership changed has its brief regenerate through the existing #064 signature
path. Reused for dissolve-survivor and sub-TAU re-placement alike.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass, field

from hrono.cluster import incubator, store
from hrono.cluster.blend import combined_vector

TAU = 0.70


@dataclass(frozen=True)
class SectionDelta:
    kind: str  # new | changed | moved | deleted
    content_hash: str
    path: str
    section_id: int | None = None  # current section (None once deleted)
    prior_node_id: int | None = None  # sticky / dissolve target cluster


@dataclass(frozen=True)
class Report:
    stayed: int = 0  # sticky re-check kept it in place
    joined: int = 0  # placement rule joined a cluster
    parked: int = 0  # sub-TAU, parked in the incubator
    deleted: int = 0  # removed with its section
    dissolved: int = 0  # clusters dissolved below two members


@dataclass
class _Batch:
    conn: sqlite3.Connection
    tree: str
    centroids: dict[int, tuple[float, ...]]  # frozen pre-batch snapshot
    working: dict[int, tuple[float, ...]]  # placement targets (dissolve pops)
    model: str
    batch: int
    affected: set[int] = field(default_factory=set)  # nodes that lost a member
    stayed: int = 0
    joined: int = 0
    parked: int = 0
    deleted: int = 0
    dissolved: int = 0


def place(
    conn: sqlite3.Connection,
    tree: str,
    deltas: Sequence[SectionDelta],
    centroids: dict[int, tuple[float, ...]],
    model_name: str,
    batch: int,
) -> Report:
    """Apply the per-chunk placement rule against pre-batch ``centroids``."""
    state = _Batch(
        conn=conn,
        tree=tree,
        centroids=centroids,
        working=dict(centroids),
        model=model_name,
        batch=batch,
    )
    for delta in deltas:
        _apply(state, delta)
    _dissolve_sweep(state)
    return Report(
        stayed=state.stayed,
        joined=state.joined,
        parked=state.parked,
        deleted=state.deleted,
        dissolved=state.dissolved,
    )


def _apply(state: _Batch, delta: SectionDelta) -> None:
    if delta.kind == "deleted":
        if delta.prior_node_id is not None:
            state.affected.add(delta.prior_node_id)
        state.deleted += 1
        return
    if delta.kind in ("changed", "moved"):
        _sticky(state, delta)
        return
    _placement(state, delta)  # new


def _sticky(state: _Batch, delta: SectionDelta) -> None:
    prior = delta.prior_node_id
    vector = _vector(state, delta)
    if vector is not None and prior is not None and prior in state.centroids:
        similarity = _dot(vector, state.centroids[prior])
        if similarity >= TAU:
            store.add_member(
                state.conn,
                prior,
                _require(delta.section_id),
                forced=False,
                similarity=similarity,
            )
            state.stayed += 1
            return
    if prior is not None:
        state.affected.add(prior)  # left its cluster; may dissolve
    _placement(state, delta)


def _placement(state: _Batch, delta: SectionDelta) -> None:
    outcome = assign_or_park(
        state.conn,
        state.tree,
        section_id=_require(delta.section_id),
        content_hash=delta.content_hash,
        path=delta.path,
        centroids=state.working,
        model_name=state.model,
        batch=state.batch,
    )
    if outcome == "joined":
        state.joined += 1
    elif outcome == "parked":
        state.parked += 1


def assign_or_park(
    conn: sqlite3.Connection,
    tree: str,
    *,
    section_id: int,
    content_hash: str,
    path: str,
    centroids: dict[int, tuple[float, ...]],
    model_name: str,
    batch: int,
) -> str:
    """Join one chunk to its best centroid >= TAU, else park it (#086).

    The shared placement primitive: the incremental rule (#085) and repair's
    dissolve/re-place (#090) both route a homeless chunk through here.
    """
    vector = combined_vector(conn, content_hash, path, model_name)
    if vector is None:
        return "skipped"
    target = _nearest(vector, centroids)
    if target is not None and target[1] >= TAU:
        store.add_member(
            conn, target[0], section_id, forced=False, similarity=target[1]
        )
        return "joined"
    incubator.park(conn, tree, content_hash, path, batch)
    return "parked"


def _dissolve_sweep(state: _Batch) -> None:
    for node_id in sorted(state.affected):
        if store.member_count(state.conn, node_id) >= 2:
            continue
        survivors = store.node_member_rows(state.conn, node_id)
        store.delete_node(state.conn, node_id)
        state.working.pop(node_id, None)
        state.dissolved += 1
        for section_id, content_hash, path in survivors:
            _placement(
                state,
                SectionDelta(
                    kind="new",
                    content_hash=content_hash,
                    path=path,
                    section_id=section_id,
                ),
            )


def _vector(state: _Batch, delta: SectionDelta) -> tuple[float, ...] | None:
    return combined_vector(
        state.conn, delta.content_hash, delta.path, state.model
    )


def _nearest(
    vector: Sequence[float], centroids: dict[int, tuple[float, ...]]
) -> tuple[int, float] | None:
    if not centroids:
        return None
    return max(
        ((nid, _dot(vector, c)) for nid, c in centroids.items()),
        key=lambda pair: pair[1],
    )


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _require(section_id: int | None) -> int:
    if section_id is None:
        raise ValueError("placement needs a current section id")
    return section_id
