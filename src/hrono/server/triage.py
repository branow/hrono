"""What needs attention in a tree, and where to go and see it (T52, #185).

Every item here is a state some earlier ticket learned to DETECT and nothing
ever learned to SHOW. A stale brief is a topic recall cannot answer from; a
parked chunk is content the map does not contain; an unparented topic is a
subtree missing from the export — the defect that shipped twice (#124, #163).

A zero is reported, never hidden. "Nothing needs attention" is the answer an
operator most wants from this page, and a blank page cannot give it.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from hrono.cluster import incubator
from hrono.cluster import store as cluster_store


@dataclass(frozen=True)
class Item:
    """One kind of work, how much of it there is, and where it lives."""

    kind: str
    count: int
    detail: str
    link: str


def survey(conn: sqlite3.Connection, tree: str) -> tuple[Item, ...]:
    """Everything worth an operator's attention in this tree, counted."""
    return (
        _unreachable(conn, tree),
        _briefless(conn, tree),
        _parked(conn, tree),
        _forced(conn, tree),
        _failed(conn, tree),
    )


def _unreachable(conn: sqlite3.Connection, tree: str) -> Item:
    """Topics nothing points at, below the top level.

    The top level is meant to be unparented — it is the root. Every level below
    it is not, and a node there with no parent takes its whole subtree out of
    the export with it.
    """
    top = conn.execute(
        "SELECT COALESCE(MAX(level), 0) AS top FROM nodes WHERE tree = ?",
        (tree,),
    ).fetchone()["top"]
    orphans = [
        node
        for level in range(int(top))
        for node in cluster_store.unparented(conn, tree, level)
    ]
    return Item(
        kind="topics nothing points at",
        count=len(orphans),
        detail="a subtree that is not in the export (#124, #163)",
        link=f"/ui/trees/{tree}/nodes/{orphans[0]}?tree={tree}"
        if orphans
        else f"/ui/trees/{tree}/graph?tree={tree}",
    )


def _briefless(conn: sqlite3.Connection, tree: str) -> Item:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM nodes n "
        "LEFT JOIN briefs b ON b.node_id = n.id "
        "WHERE n.tree = ? AND (b.node_id IS NULL OR b.stale = 1)",
        (tree,),
    ).fetchone()
    return Item(
        kind="topics with no brief, or a stale one",
        count=int(row["n"]),
        detail="recall cannot answer from these",
        link=f"/ui/trees/{tree}/graph?tree={tree}",
    )


def _parked(conn: sqlite3.Connection, tree: str) -> Item:
    return Item(
        kind="chunks in no topic",
        count=incubator.count(conn, tree),
        detail="ingested, embedded, and not on the map",
        link=f"/ui/trees/{tree}/graph?tree={tree}",
    )


def _forced(conn: sqlite3.Connection, tree: str) -> Item:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM node_members m "
        "JOIN nodes n ON n.id = m.node_id "
        "WHERE n.tree = ? AND m.forced = 1",
        (tree,),
    ).fetchone()
    return Item(
        kind="chunks placed without a score",
        count=int(row["n"]),
        detail="forced in rather than matched (#113)",
        link=f"/ui/trees/{tree}/graph?tree={tree}",
    )


def _failed(conn: sqlite3.Connection, tree: str) -> Item:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM jobs "
        "WHERE COALESCE(tree, 'default') = ? AND status = 'failed'",
        (tree,),
    ).fetchone()
    return Item(
        kind="runs that failed",
        count=int(row["n"]),
        detail="with the code and message they failed with",
        link=f"/ui/jobs?tree={tree}",
    )


def clean(items: Sequence[Item]) -> bool:
    return all(item.count == 0 for item in items)
