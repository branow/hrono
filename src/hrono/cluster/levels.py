"""The ``cluster-briefs`` op: build the next tree level up from a level's brief.

The tree is recursive — cluster -> brief -> embed briefs -> cluster the briefs
-> ... to root — so this reuses the SAME embed (#035) and cluster build (#040)
over BRIEF TEXT instead of leaf sections, proving the pipeline is level-agnostic
not section-only. For a source level N: register each level-N node's brief text
as embeddable content (embed-once by content hash), run the #035 embed op to
vectorise it, then cluster the brief vectors with the #040 build (same baked
constants) and persist level N+1 nodes whose members are the level-N node ids
(via node_children).

Path-blend (#039) is content-ONLY for briefs: a topic has no file path, so there
is nothing to blend (how-hrono-works.md) — the clustering vector is the brief's
L2-normalised content vector (alpha = 0), not a combined one, and no synthetic
path is invented. Heavy compute runs outside the #008 lock like #040.
"""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Callable, Sequence

from hrono.cluster import ClusterError, store
from hrono.cluster.placement import TAU
from hrono.embed.model import resolve_embedding_model
from hrono.embed.op import embed
from hrono.embed.store import get_vector
from hrono.ingest.identity import content_hash
from hrono.ingest.store import upsert_content
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.summarize import briefs

Builder = Callable[..., object]


def cluster_briefs(
    job: Job,
    context: JobContext,
    *,
    build: Builder | None = None,
    encoder_for: object | None = None,
) -> None:
    """Cluster a level's briefs into the next level up (members = node ids)."""
    builder = build if build is not None else _load_builder()
    tree = job.tree or "default"
    source_level = _source_level(job.scope)

    with context.database.connect() as conn:
        node_briefs = briefs.level_briefs(conn, tree, source_level)
    if not node_briefs:
        return

    with context.database.write() as conn:
        for _, text in node_briefs:
            body = text.encode("utf-8")
            upsert_content(conn, content_hash(body), body)

    embed(job, context, encoder_for=encoder_for)

    with context.database.connect() as conn:
        model_name = str(resolve_embedding_model(conn, job.scope)["name"])
        pairs = [
            (node_id, get_vector(conn, content_hash(text.encode()), model_name))
            for node_id, text in node_briefs
        ]
    ready = [(node_id, vec) for node_id, vec in pairs if vec is not None]
    if not ready:
        return

    child_ids = [node_id for node_id, _ in ready]
    vectors = [_unit(vec) for _, vec in ready]
    result = builder(vectors, init=None)

    members = [
        (label, child_ids[i], result.attached[i], sim)
        for i, (label, sim) in enumerate(
            zip(result.labels, result.assignment_similarity, strict=True)
        )
    ]
    with context.database.write() as conn:
        store.replace_level(conn, tree, source_level + 1, members)


def attach_orphans(
    job: Job,
    context: JobContext,
    *,
    encoder_for: object | None = None,
) -> tuple[tuple[int, int, float], ...]:
    """Parent every unparented leaf under its nearest node one level up.

    ATTACH-ONLY (#114): a leaf the incubator emits after ``build_tree`` has
    recursed to a root is briefed but has no parent, and ``root.md``'s children
    are rendered from parent edges — so the topic is written to the export and
    unreachable in it. Re-clustering the level above for one new leaf would
    churn every sibling's membership and invalidate the briefs over them, which
    is the incremental promise inverted; this places the leaf by the same move
    #085 makes at level 0, in the same space the level above was clustered in:
    the unit vector of its BRIEF against each candidate parent's centroid (the
    mean of its children's brief vectors), best dot product wins.

    Below TAU it still attaches, to the nearest parent, recorded as
    ``attached = 1`` — the schema's meaning of the flag (0009_nodes.sql): 1 is
    "attached by proximity", 0 is a confident, density-core placement. Parking
    is not available one level up: a node under no parent is unreachable, which
    is worse than an imperfect parent, so this mirrors the incubator's
    force-assign rather than its park.

    The flag now has a reader (#123): ``upper_misfits`` counts a below-TAU
    attached child as a misfit of its parent, and ``migrate_children`` moves it
    once a better-fitting parent exists. Before that it had none, and this
    docstring claimed the poor attachment would last "until a full rebuild
    re-derives the level" — an escape that did not exist, because nothing
    deletes an upper brief, so ``_highest_brief_level`` never drops back and
    ``build_tree`` starts at the root and stops. The true bound was FOREVER.

    The similarity is recorded on EVERY row, confident or not: it costs nothing
    (no reader to break), and a placement's score is exactly what a future
    misfit check one level up needs. That differs from ``node_members``, whose
    convention leaves it null for core members; 0012_node_children.sql records
    the divergence.

    Returns (child, parent, similarity) per attachment; empty when there is
    nothing to attach or no level above yet (a corpus whose tree is a single
    level is normal — ``_collect_root`` gives it a root first).
    """
    tree = job.tree or "default"
    with context.database.connect() as conn:
        leaf_briefs = briefs.level_briefs(conn, tree, 0)
        homeless = set(store.unparented(conn, tree, 0))
        orphans = [(nid, text) for nid, text in leaf_briefs if nid in homeless]
        parent_level = _parent_level(conn, tree)
    if not orphans or parent_level is None:
        return ()

    # every leaf brief, not just the orphans': a candidate parent's centroid is
    # the mean of its CHILDREN's brief vectors, and a sibling re-briefed since
    # the level above was clustered has no vector for its current text yet.
    with context.database.write() as conn:
        for _, text in leaf_briefs:
            body = text.encode("utf-8")
            upsert_content(conn, content_hash(body), body)
    embed(job, context, encoder_for=encoder_for)

    with context.database.connect() as conn:
        model_name = str(resolve_embedding_model(conn, job.scope)["name"])
        centroids = _parent_centroids(conn, tree, parent_level, model_name)
        vectors = {
            node_id: get_vector(
                conn, content_hash(text.encode("utf-8")), model_name
            )
            for node_id, text in orphans
        }
    if not centroids:
        return _collect_under_single_parent(
            context, tree, parent_level, orphans
        )

    attached: list[tuple[int, int, float]] = []
    with context.database.write() as conn:
        for node_id, _ in orphans:
            vector = vectors.get(node_id)
            if vector is None:
                continue
            parent, similarity = _nearest(_unit(vector), centroids)
            store.add_child(
                conn,
                parent,
                node_id,
                attached=similarity < TAU,  # 1 = by proximity, not confident
                similarity=similarity,
            )
            attached.append((node_id, parent, similarity))
    return tuple(attached)


def upper_misfits(
    conn: sqlite3.Connection, tree: str, level: int, model_name: str
) -> tuple[tuple[int, int, int], ...]:
    """Misfit counts for the parents at ``level``, measured over their children.

    The level >= 1 twin of ``monitor._misfits`` (#113), in brief space rather
    than combined-vector space: a child is a misfit of its parent when some
    other parent's centroid is nearer, OR when it was attached by proximity
    (#114) and sits below TAU. The second half is the one that matters — #114
    attaches to the NEAREST parent, so ``best_other > own`` can never fire for
    the placements this exists to review, exactly as a force-assigned member is
    invisible to the level-0 rule.

    Rows are ``(parent_id, misfits, children)``, the shape ``misfit`` stores, so
    upper levels land in the same table the rate and the repairs already read.
    """
    centroids = _parent_centroids(conn, tree, level, model_name)
    rows: list[tuple[int, int, int]] = []
    for parent_id in sorted(centroids):
        attached = store.attached_children(conn, parent_id)
        misfits = children = 0
        for child_id, vector in _child_vectors(conn, parent_id, model_name):
            children += 1
            own = _dot(vector, centroids[parent_id])
            best_other = max(
                (
                    _dot(vector, centroid)
                    for other, centroid in centroids.items()
                    if other != parent_id
                ),
                default=-1.0,
            )
            if best_other > own or (child_id in attached and own < TAU):
                misfits += 1
        rows.append((parent_id, misfits, children))
    return tuple(rows)


def migrate_children(
    conn: sqlite3.Connection, tree: str, level: int, model_name: str
) -> int:
    """Move this level's misfit children to the parent that fits them better.

    ``repair.migrate`` one level up, and the same rule: a child moves only when
    another parent actually scores higher, so a child with nowhere better keeps
    its place AND its flag, and the next pass looks again. Moving it records the
    placement unforced, so the flag keeps meaning "not yet revisited" (#123).
    """
    centroids = _parent_centroids(conn, tree, level, model_name)
    moves: list[tuple[int, int, float]] = []
    for parent_id in sorted(centroids):
        others = {p: c for p, c in centroids.items() if p != parent_id}
        if not others:
            continue
        for child_id, vector in _child_vectors(conn, parent_id, model_name):
            target, best = _nearest(vector, others)
            if best > _dot(vector, centroids[parent_id]):
                moves.append((child_id, target, best))
    for child_id, target, similarity in moves:
        store.move_child(conn, child_id, target, similarity=similarity)
    return len(moves)


def _child_vectors(
    conn: sqlite3.Connection, parent_id: int, model_name: str
) -> tuple[tuple[int, tuple[float, ...]], ...]:
    """(child id, unit brief vector) for a parent's children that have one."""
    out: list[tuple[int, tuple[float, ...]]] = []
    for row in conn.execute(
        "SELECT c.child_id AS id, b.text AS text FROM node_children c "
        "JOIN briefs b ON b.node_id = c.child_id WHERE c.parent_id = ? "
        "ORDER BY c.child_id",
        (parent_id,),
    ).fetchall():
        vector = get_vector(
            conn, content_hash(row["text"].encode("utf-8")), model_name
        )
        if vector is not None:
            out.append((int(row["id"]), _unit(vector)))
    return tuple(out)


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _collect_under_single_parent(
    context: JobContext,
    tree: str,
    parent_level: int,
    orphans: Sequence[tuple[int, str]],
) -> tuple[tuple[int, int, float], ...]:
    """Re-collect leaves under a top node that has lost all its children.

    A rebuild that re-mints leaf ids cascades the root's edges away with the
    nodes they pointed at, and ``build_tree`` does not notice: it starts at the
    highest BRIEFED level, finds the root there, and ``_collect_root`` sees one
    top node and calls the tree built. The result is a childless root and a
    level of unreachable leaves. With no children there is no centroid to place
    by, so this collects rather than places — the same move ``_collect_root``
    makes, recorded the same way (``attached`` 0, no similarity).
    """
    with context.database.connect() as conn:
        parents = [
            int(row["id"])
            for row in conn.execute(
                "SELECT id FROM nodes WHERE tree = ? AND level = ?",
                (tree, parent_level),
            ).fetchall()
        ]
    if len(parents) != 1:
        return ()
    with context.database.write() as conn:
        for node_id, _ in orphans:
            store.add_child(
                conn, parents[0], node_id, attached=False, similarity=None
            )
    return tuple((node_id, parents[0], 0.0) for node_id, _ in orphans)


def _parent_level(conn: sqlite3.Connection, tree: str) -> int | None:
    row = conn.execute(
        "SELECT MIN(level) AS level FROM nodes WHERE tree = ? AND level > 0",
        (tree,),
    ).fetchone()
    return None if row is None or row["level"] is None else int(row["level"])


def _parent_centroids(
    conn: sqlite3.Connection, tree: str, level: int, model_name: str
) -> dict[int, tuple[float, ...]]:
    """Each parent's centroid: the mean of its children's brief vectors."""
    children: dict[int, list[tuple[float, ...]]] = {}
    parents = [
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ? AND level = ? ORDER BY id",
            (tree, level),
        ).fetchall()
    ]
    for parent_id in parents:
        for row in conn.execute(
            "SELECT b.text AS text FROM node_children c "
            "JOIN briefs b ON b.node_id = c.child_id WHERE c.parent_id = ?",
            (parent_id,),
        ).fetchall():
            vector = get_vector(
                conn, content_hash(row["text"].encode("utf-8")), model_name
            )
            if vector is not None:
                children.setdefault(parent_id, []).append(_unit(vector))
    return {
        parent_id: _mean(vectors)
        for parent_id, vectors in children.items()
        if vectors
    }


def _mean(vectors: Sequence[Sequence[float]]) -> tuple[float, ...]:
    total = [
        sum(values) / len(vectors) for values in zip(*vectors, strict=True)
    ]
    return _unit(total)


def _nearest(
    vector: Sequence[float], centroids: dict[int, tuple[float, ...]]
) -> tuple[int, float]:
    scored = [
        (sum(a * b for a, b in zip(vector, centroid, strict=True)), parent_id)
        for parent_id, centroid in centroids.items()
    ]
    similarity, parent_id = max(scored)
    return parent_id, similarity


def _source_level(scope: dict[str, object]) -> int:
    level = scope.get("level")
    return int(level) if isinstance(level, int) else 0


def _unit(vec: Sequence[float]) -> tuple[float, ...]:
    norm = math.sqrt(sum(value * value for value in vec))
    if norm == 0.0:
        return tuple(vec)
    return tuple(value / norm for value in vec)


def _load_builder() -> Builder:
    try:
        from hrono.cluster.build import build_clusters
    except ImportError as exc:
        raise ClusterError("clustering backend is not installed") from exc
    return build_clusters


OPS["cluster-briefs"] = cluster_briefs
