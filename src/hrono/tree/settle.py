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
until the next trigger. ``build_tree`` then attaches it: the recursion itself
cannot see a leaf born after it (it starts at the highest briefed level, which
is already the root), so the leaf is placed under its nearest parent afterwards
and that parent is re-briefed (#114). Without that edge the topic is written to
the export but unreachable from ``root.md``, whose child listing is rendered
from parent edges. The closing embed then vectorises the node:// brief passages,
as ``maintain`` does, and the drain runs its own mini-pipeline off the #008
lock, like every other heavy step here.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence

from hrono import pins
from hrono.cluster import incubator, monitor, store
from hrono.cluster.op import cluster
from hrono.embed.model import resolve_embedding_model
from hrono.embed.op import embed
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.registry.collections.trees import DEFAULT_TREE
from hrono.summarize.brief import brief
from hrono.summarize.build_tree import build_tree

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
) -> Mapping[str, object]:
    """Warm-reconcile the tree when churn/misfit crosses the trigger."""
    tree = job.tree or DEFAULT_TREE
    with context.database.connect() as conn:
        if not (force or should_settle(conn, tree)):
            return {"settled": False, "held": 0, "released": 0}

    # WHERE a pinned chunk belongs has to be read before the rebuild, because
    # the rebuild is what erases it.
    with context.database.connect() as conn:
        anchored = anchor_members(conn, tree)

    cluster(_stage(tree, "cluster"), context, build=build)
    # the re-cluster rewrote every membership from scratch, so a hand-placed
    # chunk has just been moved by the machine. Put it back BEFORE anything
    # reads the new map: `brief` below writes summaries from membership, and a
    # brief written over the wrong members is the revert, one step removed.
    with context.database.write() as conn:
        held, released = restore_pinned(conn, tree, anchored)
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
    return {"settled": True, "held": held, "released": released}


def anchor_members(
    conn: sqlite3.Connection, tree: str
) -> dict[int, tuple[int, tuple[int, ...]]]:
    """Each section pinned IN THIS TREE: its anchor plus the anchor's company.

    The other members are what makes the anchor findable afterwards. A node is
    identified by the content of its members (#068), and a hand-move changes
    that content — so the very act the pin protects is what can retire the node
    the pin names. Its company survives the rebuild even when its id does not.

    Pins are global rows (0030 has no tree column), so the anchor's TREE is the
    scope test: a pin anchored in another tree is another tree's constraint,
    and reading it here used to make this tree's settle release it — the anchor
    was never in this tree's ``live`` set, so ``restore_pinned`` unpinned what
    a human placed somewhere this run had no business touching.
    """
    out: dict[int, tuple[int, tuple[int, ...]]] = {}
    for section_id, anchor in pins.anchors(conn, pins.MEMBERSHIP).items():
        owner = conn.execute(
            "SELECT tree FROM nodes WHERE id = ?", (anchor,)
        ).fetchone()
        if owner is not None and str(owner["tree"]) != tree:
            continue
        company = tuple(
            int(row["section_id"])
            for row in conn.execute(
                "SELECT m.section_id FROM node_members m JOIN nodes n "
                "ON n.id = m.node_id WHERE m.node_id = ? AND n.tree = ? "
                "AND m.section_id != ?",
                (anchor, tree, section_id),
            ).fetchall()
        )
        out[section_id] = (anchor, company)
    return out


def restore_pinned(
    conn: sqlite3.Connection,
    tree: str,
    anchored: dict[int, tuple[int, tuple[int, ...]]],
) -> tuple[int, int]:
    """Return each pinned section to its topic; report what could not be.

    The topic is the anchor node if it survived, and otherwise whichever node
    inherited most of its other members — that node IS the topic the operator
    pointed at, under a new id. A pin is RELEASED only when the topic is gone
    entirely: guessing at that point would park the chunk somewhere nobody
    chose, invisibly.

    Every membership read or write is scoped to THIS tree's nodes: the tables
    are global, and an unscoped delete here removed the section's membership
    in every other tree that held it.
    """
    held = released = 0
    live = {
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ?", (tree,)
        ).fetchall()
    }
    for section_id, (anchor, company) in anchored.items():
        target = anchor if anchor in live else _successor(conn, tree, company)
        if target is None:
            pins.unpin(conn, pins.MEMBERSHIP, section_id)
            released += 1
            continue
        current = _member_node(conn, tree, section_id)
        if current != target:
            conn.execute(
                "DELETE FROM node_members WHERE section_id = ? AND node_id IN "
                "(SELECT id FROM nodes WHERE tree = ?)",
                (section_id, tree),
            )
            store.add_member(
                conn, target, section_id, forced=False, similarity=None
            )
        if target != anchor:
            pins.pin(conn, pins.MEMBERSHIP, section_id, anchor=target)
        held += 1
    return held, released


def _member_node(
    conn: sqlite3.Connection, tree: str, section_id: int
) -> int | None:
    row = conn.execute(
        "SELECT m.node_id FROM node_members m JOIN nodes n "
        "ON n.id = m.node_id WHERE m.section_id = ? AND n.tree = ?",
        (section_id, tree),
    ).fetchone()
    return None if row is None else int(row["node_id"])


def _successor(
    conn: sqlite3.Connection, tree: str, company: Sequence[int]
) -> int | None:
    """The node that inherited most of a retired anchor's other members."""
    counts: dict[int, int] = {}
    for section_id in company:
        node_id = _member_node(conn, tree, section_id)
        if node_id is None:
            continue
        counts[node_id] = counts.get(node_id, 0) + 1
    if not counts:
        return None
    return max(sorted(counts), key=lambda node_id: counts[node_id])


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
