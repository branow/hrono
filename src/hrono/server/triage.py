"""What needs attention in a tree, and where to go and see it (T52, #185).

Every item here is a state some earlier ticket learned to DETECT and nothing
ever learned to SHOW. A stale brief is a topic recall cannot answer from; a
parked section is content the map does not contain; an unparented topic is a
subtree missing from the export — the defect that shipped twice (#124, #163).

A zero is reported, never hidden. "Nothing needs attention" is the answer an
operator most wants from this page, and a blank page cannot give it.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from hrono import pins
from hrono.cluster import incubator
from hrono.cluster import store as cluster_store
from hrono.summarize import briefs


@dataclass(frozen=True)
class Item:
    """One kind of work, how much of it there is, and where it lives."""

    kind: str
    count: int
    detail: str
    link: str
    # The same finding as a sentence, so a zero reads as an answer and a
    # non-zero reads as a task: `{n}` is the count, `one` the singular form.
    clear: str = ""
    one: str = ""
    many: str = ""

    @property
    def said(self) -> str:
        if self.count == 0:
            return self.clear
        if self.count == 1:
            return self.one
        return self.many.format(n=self.count)


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
        kind="topics cut off from the root",
        count=len(orphans),
        detail="Everything beneath them is missing from the export.",
        clear="Every topic can be reached from the root",
        one="1 topic is cut off from the root",
        many="{n} topics are cut off from the root",
        link=f"/ui/trees/{tree}/nodes/{orphans[0]}?tree={tree}"
        if orphans
        else f"/ui/trees/{tree}/graph?tree={tree}",
    )


def unanswerable(conn: sqlite3.Connection, tree: str) -> list[int]:
    """Topics recall cannot answer from: no brief, a stale one, or a reply
    that is not a brief at all (#217) — a pinned brief is a person's, and
    counts as written. The one rule the Health page and the outline share."""
    held = pins.pinned(conn, pins.BRIEF)
    rows = conn.execute(
        "SELECT n.id AS id, b.node_id AS has, b.stale AS stale, "
        f"b.flagged AS flagged, b.text AS text, {briefs.TEMPLATE} AS template "
        "FROM nodes n "
        "LEFT JOIN briefs b ON b.node_id = n.id WHERE n.tree = ? ORDER BY n.id",
        (tree,),
    ).fetchall()
    return [
        int(row["id"])
        for row in rows
        if int(row["id"]) not in held
        and (
            row["has"] is None
            or row["stale"]
            or briefs.refusal(
                conn,
                int(row["id"]),
                row["flagged"],
                row["text"],
                row["template"],
            )
        )
    ]


def _briefless(conn: sqlite3.Connection, tree: str) -> Item:
    missing = unanswerable(conn, tree)
    people = sum(1 for node in missing if briefs.settled(conn, node))
    detail = (
        "Recall cannot answer from them until a sync rewrites them."
        if not people
        else "Recall cannot answer from them until they are rewritten; "
        f"{people} {'needs' if people == 1 else 'need'} a person."
    )
    return Item(
        kind="topics with no usable brief, or a stale one",
        count=len(missing),
        detail=detail,
        clear="Every topic has a brief that holds",
        one="1 topic has no usable brief, or a stale one",
        many="{n} topics have no usable brief, or a stale one",
        link=f"/ui/trees/{tree}/triage?tree={tree}#briefs"
        if missing
        else f"/ui/trees/{tree}/graph?tree={tree}",
    )


def _parked(conn: sqlite3.Connection, tree: str) -> Item:
    return Item(
        kind="sections waiting for a topic",
        count=incubator.count(conn, tree),
        detail="Read and embedded, but not on the map yet.",
        clear="No sections are waiting for a topic",
        one="1 section is waiting for a topic",
        many="{n} sections are waiting for a topic",
        link=f"/ui/trees/{tree}/triage?tree={tree}#waiting",
    )


def _forced(conn: sqlite3.Connection, tree: str) -> Item:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM node_members m "
        "JOIN nodes n ON n.id = m.node_id "
        "WHERE n.tree = ? AND m.forced = 1",
        (tree,),
    ).fetchone()
    return Item(
        kind="sections placed without a score",
        count=int(row["n"]),
        detail="Filed by rule rather than matched to a topic.",
        clear="Every section was placed by a score",
        one="1 section was placed without a score",
        many="{n} sections were placed without a score",
        link=f"/ui/trees/{tree}/triage?tree={tree}#placed",
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
        detail="Open Runs for the code and message each one failed with.",
        clear="No run has failed",
        one="1 run has failed",
        many="{n} runs have failed",
        link=f"/ui/jobs?tree={tree}",
    )


def clean(items: Sequence[Item]) -> bool:
    return all(item.count == 0 for item in items)
