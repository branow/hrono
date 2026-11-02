"""Which topics an insights pass would review, and what the passes would cost.

Insights is a step where a strong model reviews a big area of a tree and its
findings are written into the area's brief. This module is the part that
decides WHERE: the characters of briefs under a topic that no pass has covered
(the counter), the topics that reach the tree's threshold, and the price of
those passes. Running a pass is not here.

The counter is derived from the stored briefs and the pass rows
(`insights_passes`), never kept: a stored number drifts when a brief is edited
by hand, reverted or undone. A brief is COVERED for a topic when it was
written no later than a pass on that topic or on any topic between them; a pass
on a child therefore takes its whole subtree out of the parent's count, and a
brief rewritten after the pass counts again. The topic's own brief is not
counted: the counter is what a pass on the topic would newly read below it.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from hrono import naming
from hrono.registry import store
from hrono.summarize.resolve import INSIGHTS_ROLE

# Measured on Opus at API prices on a 36-topic unit: $2.43 a review (the
# spread over tries was $1.79-$3.25) and $0.39 for the extend call that
# writes the findings into the brief (`dev/research/insights-recipe.md`).
REVIEW_USD = 2.43
EXTEND_USD = 0.39

# Sorts after every real timestamp: a pass planned but not yet run.
_PLANNED = "9999"


@dataclass(frozen=True)
class Pass:
    node: int
    level: int
    characters: int


@dataclass(frozen=True)
class Plan:
    """The passes a tree's next build would run, and what they cost."""

    on: bool
    threshold: int
    passes: tuple[Pass, ...]
    names: dict[int, str]
    usd: float
    basis: str
    note: str | None


def plan_for(
    conn: sqlite3.Connection,
    tree: str,
    on: bool,
    threshold: int,
) -> Plan:
    """The passes for a tree with insights ``on`` at ``threshold``."""
    if not on:
        return Plan(on, threshold, (), {}, 0.0, "insights are off", None)
    passes = passes_for(conn, tree, threshold)
    names = naming.names(conn, [one.node for one in passes])
    usd, basis, note = _cost(conn, len(passes))
    return Plan(on, threshold, passes, names, usd, basis, note)


def passes_for(
    conn: sqlite3.Connection, tree: str, threshold: int
) -> tuple[Pass, ...]:
    """The topics that would get a pass, lowest level first.

    Walks up level by level as a build does: a topic that reaches the
    threshold is reviewed, its subtree then counts for nothing above it. The
    root (the top level) is always reviewed, over whatever is left.
    """
    tops = _Tree(conn, tree)
    if not tops.top:
        return ()
    found: list[Pass] = []
    for level in range(1, tops.top + 1):
        for node in tops.at(level):
            counted = tops.unreviewed(node)
            if counted >= threshold or level == tops.top:
                found.append(Pass(node, level, counted))
                tops.planned.add(node)
    return tuple(found)


def unreviewed(conn: sqlite3.Connection, tree: str) -> dict[int, int]:
    """Characters of unreviewed brief below each topic of the tree."""
    held = _Tree(conn, tree)
    return {node: held.unreviewed(node) for node in held.level}


class _Tree:
    """A tree's shape, briefs and passes, read once."""

    def __init__(self, conn: sqlite3.Connection, tree: str) -> None:
        self.level = {
            int(r["id"]): int(r["level"])
            for r in conn.execute(
                "SELECT id, level FROM nodes WHERE tree = ?", (tree,)
            )
        }
        self.top = max(self.level.values(), default=0)
        self.children: dict[int, list[int]] = {}
        for r in conn.execute(
            "SELECT c.parent_id, c.child_id FROM node_children c "
            "JOIN nodes n ON n.id = c.parent_id WHERE n.tree = ?",
            (tree,),
        ):
            self.children.setdefault(int(r["parent_id"]), []).append(
                int(r["child_id"])
            )
        self.brief = {
            int(r["node_id"]): (int(r["size"]), str(r["created_at"]))
            for r in conn.execute(
                "SELECT b.node_id, length(b.text) AS size, b.created_at "
                "FROM briefs b JOIN nodes n ON n.id = b.node_id "
                "WHERE n.tree = ?",
                (tree,),
            )
        }
        self.passed = {
            int(r["node_id"]): str(r["at"])
            for r in conn.execute(
                "SELECT p.node_id, MAX(p.passed_at) AS at "
                "FROM insights_passes p JOIN nodes n ON n.id = p.node_id "
                "WHERE n.tree = ? GROUP BY p.node_id",
                (tree,),
            )
        }
        self.planned: set[int] = set()

    def at(self, level: int) -> list[int]:
        return sorted(n for n, lv in self.level.items() if lv == level)

    def unreviewed(self, node: int) -> int:
        return self._below(node, self._passed(node), {node})

    def _passed(self, node: int) -> str:
        if node in self.planned:
            return _PLANNED
        return self.passed.get(node, "")

    def _below(self, node: int, covered: str, seen: set[int]) -> int:
        total = 0
        for child in self.children.get(node, ()):
            if child in seen:
                continue
            seen.add(child)
            cut = max(covered, self._passed(child))
            size, written = self.brief.get(child, (0, ""))
            total += size if written > cut else 0
            total += self._below(child, cut, seen)
        return total


def _cost(
    conn: sqlite3.Connection, count: int
) -> tuple[float, str, str | None]:
    """Dollars, what they rest on, and a note when no pass could run."""
    usd = round(count * (REVIEW_USD + EXTEND_USD), 2)
    basis = (
        f"${REVIEW_USD} a review and ${EXTEND_USD} to extend the brief, "
        "measured on Opus at API prices"
    )
    models = [
        _config(row)
        for row in store.list_all(conn, "models")
        if _config(row).get("role") == INSIGHTS_ROLE
    ]
    if not models:
        return (
            usd,
            basis,
            "no model has the role insights: nothing runs until one does",
        )
    provider = _provider(conn, str(models[0].get("connection")))
    if provider == "claude-code":
        basis += (
            "; a subscription is not billed per token, so this is an "
            "estimate of what the API would charge"
        )
    return usd, basis, None


def _config(row: sqlite3.Row) -> dict[str, object]:
    return dict(json.loads(row["config"]))


def _provider(conn: sqlite3.Connection, connection: str) -> str | None:
    row = store.get(conn, "connections", connection)
    if row is None:
        return None
    return str(_config(row).get("provider"))
