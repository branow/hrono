"""The ``build-tree`` controller: recurse brief levels up to a single root.

Given a leaf level of briefs (#059), drive #060 (embed + cluster the level's
briefs into the next level up) then #061 (brief-upper the new level), one level
per pass, until the tree collapses to a single root node. Rebuilds bottom-up:
starts at the HIGHEST level that already has briefs, so a fresh corpus recurses
from level 0 and a re-run over an already-built tree starts at the root and does
nothing (idempotent, no duplicate levels — never rebuilding a level under an
already-built parent, per #060's node_children cascade constraint).

A leaf that appears AFTER the recursion — the incubator's drain emits them
(#095) — cannot be seen by it: the pass starts at the highest briefed level,
which is already the root. Such leaves are attached to their nearest parent
afterwards and that parent is re-briefed (#114, attach-only); without the edge
the topic is written to the export but unreachable from ``root.md``.

Termination is guarded four ways so a pathological corpus cannot spin: a level
of one node IS the root; a level too sparse to cluster raises ``ClusterError``
near the root and stops (declaring the current top the root); a level that fails
to REDUCE the node count is discarded and stops; and depth is hard-capped at
``D_MAX`` (clustering-lifecycle.md). Deterministic under the fixed clustering
seed, except over tied points (``cluster.build``: a level of identical briefs).

ONLY ``TooFewPoints`` stops the climb (#131). It used to catch ``ClusterError``
broadly, and ``build_clusters`` raises that when the reduction fails, when the
clusterer fails and when the backend is not installed — so a BROKEN backend at
any level was read as "the current top is the root" and produced a TRUNCATED
tree reported as success. #112 hit the same defect one level down and created
the type that tells the two apart: a ladder that declines to reduce is not a
failure, and everything else is.
"""

from __future__ import annotations

import sqlite3

from hrono.cluster import TooFewPoints, store
from hrono.cluster import store as cluster_store
from hrono.cluster.levels import attach_orphans, cluster_briefs
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import Completion
from hrono.summarize import UnreachableTree
from hrono.summarize.brief_upper import brief_upper

D_MAX = 5
_DEFAULT_TREE = "default"


def build_tree(
    job: Job,
    context: JobContext,
    *,
    client: Completion | None = None,
    encoder_for: object | None = None,
    build: object | None = None,
) -> None:
    """Recurse the brief levels of a tree up to a single root node."""
    tree = job.tree or _DEFAULT_TREE
    with context.database.connect() as conn:
        start = _highest_brief_level(conn, tree)
    if start is None:
        return

    level = start
    while level < D_MAX:
        with context.database.connect() as conn:
            current = _count(conn, tree, level)
        if current <= 1:
            break  # a single node at this level is the root

        try:
            cluster_briefs(
                _level_job(tree, level),
                context,
                build=build,
                encoder_for=encoder_for,
            )
        except TooFewPoints:
            break  # too sparse to reduce further -> the current top IS the root

        with context.database.connect() as conn:
            formed = _count(conn, tree, level + 1)
        if formed == 0 or formed >= current:
            with context.database.write() as conn:
                _drop_level(conn, tree, level + 1)  # not a real abstraction
            break

        brief_upper(_level_job(tree, level + 1), context, client=client)
        level += 1

    _collect_root(context, tree, client)
    _adopt_late_leaves(context, tree, client, encoder_for)
    _require_reachable(context, tree)


def _require_reachable(context: JobContext, tree: str) -> None:
    """Refuse to call a tree built while any topic is linked from nothing.

    ``root.md``'s children are rendered from parent EDGES, so an unparented
    node is written to the export and unreachable in it. Every route that
    produces one has been closed as it was found (#114, #124), and this is the
    guard for the routes nobody has thought of yet: reporting success over an
    unreachable map is the shape F16, F20 and F29 all share.

    EVERY level below the top, not just the leaves (#163). Checking only level
    0 let a whole subtree hang off nothing and still pass: the orphan was an
    upper node, so its own children were parented — to it — and the leaf-level
    check saw a tidy map. This guard is the one that would have caught that,
    and did not.
    """
    with context.database.connect() as conn:
        top = _top_level(conn, tree)
        if top == 0:
            return  # a one-topic tree: the leaf IS the root (#112)
        orphans = tuple(
            node
            for level in range(top)
            for node in store.unparented(conn, tree, level)
        )
    if orphans:
        raise UnreachableTree(
            f"{len(orphans)} topic(s) unreachable from the root: "
            f"{list(orphans)[:10]}"
        )


def _top_level(conn: sqlite3.Connection, tree: str) -> int:
    row = conn.execute(
        "SELECT MAX(level) AS top FROM nodes WHERE tree = ?", (tree,)
    ).fetchone()
    return 0 if row is None or row["top"] is None else int(row["top"])


def _adopt_late_leaves(
    context: JobContext,
    tree: str,
    client: Completion | None,
    encoder_for: object | None,
) -> None:
    """Attach nodes born or orphaned after the recursion, then re-brief.

    The incubator emits new leaves long after the tree was built (#095), and the
    recursion cannot see them: it starts at the highest BRIEFED level, finds one
    root there and stops. The leaf is briefed and written to the export but
    nothing links to it from ``root.md`` (#114). ATTACH-ONLY, per #085's rule
    one level up — see ``levels.attach_orphans``.

    The parent gains a child, so its brief no longer describes its children:
    ``brief_upper`` re-runs for that level, which #064 makes cheap — only the
    node whose child-set signature changed is regenerated, its siblings are
    skipped. Leaving it stale instead would ship a parent brief that omits the
    topic underneath it, which is this ticket's harm one level up.
    """
    with context.database.connect() as conn:
        top = _top_level(conn, tree)
    attached: tuple[tuple[int, int, float], ...] = ()
    # every level, bottom up: an orphan at level N is adopted before level N+1
    # is swept, so a subtree that had come loose is whole again by the time its
    # own parent is looked at (#163).
    for level in range(top):
        attached += attach_orphans(
            _level_job(tree, level),
            context,
            level=level,
            encoder_for=encoder_for,
        )
    if not attached:
        return
    with context.database.connect() as conn:
        levels = sorted(
            {_level_of(conn, parent) for _, parent, _ in attached} - {None}
        )
    for level in levels:
        brief_upper(_level_job(tree, int(level)), context, client=client)


def _level_of(conn: sqlite3.Connection, node_id: int) -> int | None:
    row = conn.execute(
        "SELECT level FROM nodes WHERE id = ?", (node_id,)
    ).fetchone()
    return None if row is None else int(row["level"])


def _collect_root(
    context: JobContext, tree: str, client: Completion | None
) -> None:
    """Guarantee ONE root: if recursion stopped with >1 top node (non-reducing
    or D_MAX cases), parent them all under a single root and brief it.

    This is a COLLECT, not a cluster — it runs once, only when clustering has
    genuinely stopped reducing, so the stored tree always has the single
    orienting root the spec (and export/recall) require. The root may sit one
    level above D_MAX: D_MAX bounds the CLUSTERED levels, the root is always
    allowed on top.
    """
    with context.database.connect() as conn:
        top = _highest_node_level(conn, tree)
        top_nodes = [] if top is None else _nodes_at(conn, tree, top)
    if len(top_nodes) <= 1:
        return
    with context.database.write() as conn:
        cluster_store.replace_level(
            conn,
            tree,
            top + 1,
            [(0, node_id, False, None) for node_id in top_nodes],
        )
    brief_upper(_level_job(tree, top + 1), context, client=client)


def _level_job(tree: str, level: int) -> Job:
    return Job(
        id=f"build-tree-{level}",
        parent_id=None,
        tree=tree,
        op="build-tree",
        scope={"level": level},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


def _highest_brief_level(conn: sqlite3.Connection, tree: str) -> int | None:
    row = conn.execute(
        "SELECT MAX(n.level) AS level FROM nodes n "
        "JOIN briefs b ON b.node_id = n.id WHERE n.tree = ?",
        (tree,),
    ).fetchone()
    return None if row is None or row["level"] is None else int(row["level"])


def _highest_node_level(conn: sqlite3.Connection, tree: str) -> int | None:
    row = conn.execute(
        "SELECT MAX(level) AS level FROM nodes WHERE tree = ?", (tree,)
    ).fetchone()
    return None if row is None or row["level"] is None else int(row["level"])


def _nodes_at(conn: sqlite3.Connection, tree: str, level: int) -> list[int]:
    return [
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ? AND level = ? ORDER BY id",
            (tree, level),
        ).fetchall()
    ]


def _count(conn: sqlite3.Connection, tree: str, level: int) -> int:
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM nodes WHERE tree = ? AND level = ?",
            (tree, level),
        ).fetchone()[0]
    )


def _drop_level(conn: sqlite3.Connection, tree: str, level: int) -> None:
    conn.execute(
        "DELETE FROM nodes WHERE tree = ? AND level = ?", (tree, level)
    )


OPS["build-tree"] = build_tree
