"""The ``settle`` op (#091, T39): the rare warm reconcile that re-tidies drift.

The last M7 piece. Incremental placement (#085) drifts the stored clusters over
many batches; ``settle`` periodically does a full WARM rebuild to re-tidy them,
applying only the membership delta so briefs mostly survive. It is a maintenance
pass, NOT an update path — triggered, not run every batch.

Trigger (T39.1): the accumulated per-tree drift (#087's counter) crossing
CHURN_THRESHOLD, OR a misfit backstop — the #089 global misfit rate above ~2x
the post-build baseline (the settled RECONCILE trigger) even when churn is low.
The counter resets after a settle; the baseline is the post-build reference and
is NOT reset.

The rebuild reuses settled ops: ``cluster`` warm-starts UMAP from the stored
coords (#040's ``init`` seam) and ``replace_tree`` applies the membership diff
while #068's signature reconcile keeps unchanged nodes' ids and briefs;
``brief`` and ``build_tree`` then re-brief ONLY the membership-changed nodes
(via #064). So a settle over an unchanged corpus is a near-no-op — the warm
start reproduces the layout, ~0 delta, ~0 re-briefs. Heavy compute runs inside
those ops, off the #008 lock. Manual-edit pins (M9) would be honoured as fixed
here; none exist yet.

A reconcile is also the natural moment to re-home strays (#095): the rebuild
itself re-clusters every parked chunk and ``cluster`` sweeps the pool rows it
obsoletes, and a ``drain`` clears any residue the rebuild could not reach. Its
place in the chain is fixed by what it needs and what it produces — AFTER the
embed pass that makes a late chunk placeable at all, and BEFORE ``brief``, so a
leaf node the drain emits is briefed in this same settle rather than left blank
until the next trigger. It is NOT parented: ``build_tree`` starts at the highest
briefed level and never revisits level 0, so a leaf born after the recursion
hangs under no parent. It is still written to the export (#096 gives every
parentless node its own directory), but nothing links to it from ``root.md``, so
an agent walking the map from the root never reaches it (backlog #114). The
closing
embed then vectorises the node:// brief passages, as ``maintain`` does. The
drain runs its own mini-pipeline off the #008 lock, like every other heavy step
here.
"""

from __future__ import annotations

import sqlite3

from hrono.cluster import incubator, monitor, store
from hrono.cluster.op import cluster
from hrono.embed.model import resolve_embedding_model
from hrono.embed.op import embed
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.summarize.brief import brief
from hrono.summarize.build_tree import build_tree

_DEFAULT_TREE = "default"
CHURN_THRESHOLD = 50  # accumulated drift points since the last settle
MISFIT_FACTOR = 2.0  # global misfit above 2x baseline forces a reconcile


def settle(
    job: Job,
    context: JobContext,
    *,
    force: bool = False,
    build: object | None = None,
    encoder_for: object | None = None,
    client: object | None = None,
) -> None:
    """Warm-reconcile the tree when churn/misfit crosses the trigger."""
    tree = job.tree or _DEFAULT_TREE
    with context.database.connect() as conn:
        if not (force or should_settle(conn, tree)):
            return

    cluster(_stage(tree, "cluster"), context, build=build)
    embed(_stage(tree, "embed"), context, encoder_for=encoder_for)
    with context.database.connect() as conn:
        model = str(resolve_embedding_model(conn, job.scope)["name"])
    incubator.drain(context.database, tree, model)
    brief(_stage(tree, "brief"), context, client=client)
    build_tree(
        _stage(tree, "build-tree"),
        context,
        client=client,
        encoder_for=encoder_for,
        build=build,
    )
    embed(_stage(tree, "embed"), context, encoder_for=encoder_for)

    with context.database.write() as conn:
        monitor.refresh(
            conn, tree, model, sorted(store.node_centroids(conn, tree, model))
        )
        _reset_drift(conn, tree)


def should_settle(conn: sqlite3.Connection, tree: str) -> bool:
    """True when accumulated churn or the global-misfit backstop trips."""
    if _drift(conn, tree) >= CHURN_THRESHOLD:
        return True
    base = monitor.baseline(conn, tree)
    return (
        base is not None
        and base > 0
        and monitor.global_rate(conn, tree) > MISFIT_FACTOR * base
    )


def _drift(conn: sqlite3.Connection, tree: str) -> int:
    row = conn.execute(
        "SELECT drift FROM tree_batch WHERE tree = ?", (tree,)
    ).fetchone()
    return int(row["drift"]) if row is not None else 0


def _reset_drift(conn: sqlite3.Connection, tree: str) -> None:
    conn.execute(
        "INSERT INTO tree_batch(tree, batch, drift) VALUES (?, 0, 0) "
        "ON CONFLICT(tree) DO UPDATE SET drift = 0",
        (tree,),
    )


def _stage(tree: str, op: str) -> Job:
    return Job(
        id=f"settle-{op}",
        parent_id=None,
        tree=tree,
        op=op,
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


OPS["settle"] = settle
