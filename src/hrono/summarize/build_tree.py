"""The ``build-tree`` controller: recurse brief levels up to a single root.

Given a leaf level of briefs (#059), drive #060 (embed + cluster the level's
briefs into the next level up) then #061 (brief-upper the new level), one level
per pass, until the tree collapses to a single root node. Rebuilds bottom-up:
starts at the HIGHEST level that already has briefs, so a fresh corpus recurses
from level 0 and a re-run over an already-built tree starts at the root and does
nothing (idempotent, no duplicate levels — never rebuilding a level under an
already-built parent, per #060's node_children cascade constraint).

Termination is guarded four ways so a pathological corpus cannot spin: a level
of one node IS the root; a level too sparse to cluster raises ``ClusterError``
near the root and stops (declaring the current top the root); a level that fails
to REDUCE the node count is discarded and stops; and depth is hard-capped at
``D_MAX`` (clustering-lifecycle.md). Deterministic under the fixed clustering
seed.
"""

from __future__ import annotations

import sqlite3

from hrono.cluster import ClusterError
from hrono.cluster.levels import cluster_briefs
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import Completion
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
        except ClusterError:
            break  # too sparse to cluster near the root -> current top is root

        with context.database.connect() as conn:
            formed = _count(conn, tree, level + 1)
        if formed == 0 or formed >= current:
            with context.database.connect() as conn, conn:
                _drop_level(conn, tree, level + 1)  # not a real abstraction
            break

        brief_upper(_level_job(tree, level + 1), context, client=client)
        level += 1


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
