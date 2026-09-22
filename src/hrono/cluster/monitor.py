"""The misfit-rate monitor (#089, T37): the health signal repair/settle read.

After a change batch, ``monitor`` measures the MISFIT RATE — how many chunks sit
in a cluster whose centroid is not their nearest. All vectors are unit length
and a centroid is the renormalized mean of its members' combined vectors, so
the decision is a plain dot product: for chunk c in cluster K, ``own = c.K`` and
``best_other = max over J != K of c.J``; c is a misfit iff ``best_other > own``.

A FORCE-ASSIGNED member (#086 T35.3) is the exception that rule cannot see: it
was attached to its NEAREST centroid ignoring TAU, so ``own`` is the maximum by
construction and ``best_other > own`` is never true however alien it is. Such a
member is a misfit while its own similarity is below TAU — which is what finally
makes 0017's promise ("flagged so the misfit monitor re-checks it preferentially
and a mis-placed pioneer migrates once its real siblings form") readable (#113).

Cost stays scale-independent: the per-cluster counts persist in ``misfit``, and
a batch re-checks only the DIRTY clusters it touched plus a bounded per-batch
sample (deterministic, and preferring clusters that hold a forced member) — the
global rate aggregates the stored rows without rescanning the corpus. The first
(post-build) run captures the baseline global rate; a fresh tree's rate is
nonzero by nature (HDBSCAN edge members lean toward neighbours), so repair (T38)
and settle (T39) compare RELATIVE to that baseline.
Monitor only MEASURES — acting on the rate is repair/settle.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime

from hrono.cluster import store
from hrono.cluster.blend import combined_vector
from hrono.cluster.placement import TAU
from hrono.embed.model import resolve_embedding_model
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext

SAMPLE_SIZE = 32  # bounded per-batch re-check beyond the dirty clusters


def monitor(job: Job, context: JobContext) -> None:
    """Refresh misfit counts for the batch's dirty clusters (+ a sample)."""
    tree = job.tree or "default"
    dirty = [int(node_id) for node_id in job.scope.get("dirty", [])]
    with context.database.write() as conn:
        model = str(resolve_embedding_model(conn, job.scope)["name"])
        centroids = store.node_centroids(conn, tree, model)
        all_nodes = sorted(centroids)
        first_run = baseline(conn, tree) is None
        if first_run:
            targets: Sequence[int] = all_nodes
        else:
            batch = _batch(conn, tree)
            targets = sorted(
                set(dirty)
                | set(
                    sample(
                        all_nodes,
                        dirty,
                        SAMPLE_SIZE,
                        batch,
                        store.forced_holders(conn, tree),
                    )
                )
            )
        write_misfits(
            conn, tree, _misfits(conn, tree, model, targets, centroids)
        )
        if first_run:
            capture_baseline(conn, tree, global_rate(conn, tree))


def refresh(
    conn: sqlite3.Connection,
    tree: str,
    model_name: str,
    node_ids: Sequence[int],
) -> None:
    """Recompute and store misfit counts for exactly ``node_ids``."""
    centroids = store.node_centroids(conn, tree, model_name)
    write_misfits(
        conn, tree, _misfits(conn, tree, model_name, node_ids, centroids)
    )


def _misfits(
    conn: sqlite3.Connection,
    tree: str,
    model_name: str,
    node_ids: Sequence[int],
    centroids: dict[int, tuple[float, ...]],
) -> tuple[tuple[int, int, int], ...]:
    rows: list[tuple[int, int, int]] = []
    for node_id in node_ids:
        own_centroid = centroids.get(node_id)
        forced = store.forced_members(conn, node_id)
        misfits = members = 0
        for sid, content_hash, path in store.node_member_rows(conn, node_id):
            vector = combined_vector(conn, content_hash, path, model_name)
            if vector is None:
                continue
            members += 1
            own = _dot(vector, own_centroid) if own_centroid else -1.0
            best_other = max(
                (
                    _dot(vector, centroid)
                    for other, centroid in centroids.items()
                    if other != node_id
                ),
                default=-1.0,
            )
            if best_other > own or (sid in forced and own < TAU):
                misfits += 1
        rows.append((node_id, misfits, members))
    return tuple(rows)


def write_misfits(
    conn: sqlite3.Connection,
    tree: str,
    rows: Iterable[tuple[int, int, int]],
) -> None:
    now = _now()
    for node_id, misfits, members in rows:
        conn.execute(
            "INSERT INTO misfit(tree, node_id, misfits, members, updated_at) "
            "VALUES (?, ?, ?, ?, ?) ON CONFLICT(tree, node_id) DO UPDATE SET "
            "misfits = excluded.misfits, members = excluded.members, "
            "updated_at = excluded.updated_at",
            (tree, node_id, misfits, members, now),
        )


def global_rate(conn: sqlite3.Connection, tree: str) -> float:
    """The corpus misfit rate aggregated over the stored per-cluster counts."""
    row = conn.execute(
        "SELECT COALESCE(SUM(misfits), 0) AS m, COALESCE(SUM(members), 0) AS t "
        "FROM misfit WHERE tree = ?",
        (tree,),
    ).fetchone()
    return _rate(int(row["m"]), int(row["t"]))


def cluster_rate(conn: sqlite3.Connection, tree: str, node_id: int) -> float:
    """One cluster's misfit fraction of its members (0.0 if unmeasured)."""
    row = conn.execute(
        "SELECT misfits, members FROM misfit WHERE tree = ? AND node_id = ?",
        (tree, node_id),
    ).fetchone()
    if row is None:
        return 0.0
    return _rate(int(row["misfits"]), int(row["members"]))


def capture_baseline(conn: sqlite3.Connection, tree: str, rate: float) -> None:
    conn.execute(
        "INSERT INTO tree_batch(tree, batch, baseline) VALUES (?, 0, ?) "
        "ON CONFLICT(tree) DO UPDATE SET baseline = excluded.baseline",
        (tree, rate),
    )


def baseline(conn: sqlite3.Connection, tree: str) -> float | None:
    row = conn.execute(
        "SELECT baseline FROM tree_batch WHERE tree = ?", (tree,)
    ).fetchone()
    return (
        None
        if row is None or row["baseline"] is None
        else float(row["baseline"])
    )


def sample(
    node_ids: Sequence[int],
    exclude: Sequence[int],
    k: int,
    seed: int,
    prefer: Iterable[int] = (),
) -> tuple[int, ...]:
    """A deterministic, bounded pick of non-dirty clusters (batch-stamped).

    ``prefer`` jumps the round-robin: clusters holding a force-assigned member
    are the ones 0017 promised to re-check preferentially, and a pioneer only
    leaves once someone looks at it again (#113).
    """
    candidates = sorted(set(node_ids) - set(exclude))
    if not candidates or k <= 0:
        return ()
    if k >= len(candidates):
        return tuple(candidates)
    preferred = set(prefer)
    first = [n for n in candidates if n in preferred][:k]
    rest = [n for n in candidates if n not in preferred]
    room = k - len(first)
    if room <= 0 or not rest:
        return tuple(first)
    if room >= len(rest):
        return tuple(first + rest)
    start = seed % len(rest)
    return tuple(first + [rest[(start + i) % len(rest)] for i in range(room)])


def _batch(conn: sqlite3.Connection, tree: str) -> int:
    row = conn.execute(
        "SELECT batch FROM tree_batch WHERE tree = ?", (tree,)
    ).fetchone()
    return int(row["batch"]) if row is not None else 0


def _rate(misfits: int, total: int) -> float:
    return misfits / total if total else 0.0


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _now() -> str:
    return datetime.now(UTC).isoformat()


OPS["monitor"] = monitor
