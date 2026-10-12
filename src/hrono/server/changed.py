"""What one run changed in its tree, read from the change journal.

The run page shows it so a sync can be seen to be incremental: which topics
it touched, out of how many, and what happened to each. It is read from
``changes`` (``db/journal.py``), the same record a revert undoes, so what the
page says the run did is what reverting it takes back.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from dataclasses import dataclass, field

from hrono.db import journal

# What a topic went through, strongest first: a topic both made and
# rewritten in one run is shown as new.
NEW, REWRITTEN, REGROUPED, RETIRED = "new", "rewritten", "regrouped", "retired"
_RANK = {NEW: 0, RETIRED: 1, REWRITTEN: 2, REGROUPED: 3}

# Which column of a journaled table names the topic a row is about; a
# table whose rowid IS the topic id says None.
_TOPIC_OF = {
    "nodes": None,
    "briefs": None,
    "node_members": "node_id",
    "node_children": "parent_id",
}


@dataclass(frozen=True)
class Changed:
    """One run's changes, as the run page shows them."""

    run: str
    tree: str
    total: int  # the topics the tree has now
    topics: dict[int, str] = field(default_factory=dict)  # id -> what happened
    files: dict[str, int] = field(default_factory=dict)  # added, removed
    rows: int = 0
    reverted: str | None = None
    blocker: str | None = None

    def count(self, what: str) -> int:
        return sum(1 for done in self.topics.values() if done == what)


def changed(conn: sqlite3.Connection, run: str, tree: str) -> Changed | None:
    """What ``run`` changed in ``tree``; None when it changed nothing."""
    entries = conn.execute(
        "SELECT tbl, op, row, before FROM changes WHERE run = ? ORDER BY id",
        (run,),
    ).fetchall()
    if not entries:
        return None
    topics: dict[int, str] = {}
    files: Counter[str] = Counter()
    for entry in entries:
        table, op = str(entry["tbl"]), str(entry["op"])
        is_section = table == "sections" and op in ("insert", "delete")
        if is_section and _is_file(conn, entry):
            files["added" if op == "insert" else "removed"] += 1
        if table not in _TOPIC_OF:
            continue
        topic = _topic(conn, entry)
        if topic is None:
            continue
        done = _what(table, op)
        if topic not in topics or _RANK[done] < _RANK[topics[topic]]:
            topics[topic] = done
    reverted = conn.execute(
        "SELECT reverted_at FROM reverts WHERE run = ?", (run,)
    ).fetchone()
    total = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE tree = ?", (tree,)
    ).fetchone()[0]
    return Changed(
        run=run,
        tree=tree,
        total=int(total),
        topics=topics,
        files=dict(files),
        rows=len(entries),
        reverted=str(reverted[0]) if reverted else None,
        blocker=None if reverted else journal.blocker(conn, run),
    )


def _what(table: str, op: str) -> str:
    if table == "nodes":
        return {"insert": NEW, "delete": RETIRED}.get(op, REGROUPED)
    if table == "briefs":
        return REWRITTEN
    return REGROUPED


def _topic(conn: sqlite3.Connection, entry: sqlite3.Row) -> int | None:
    """The topic a journaled row is about, from the row or its old copy."""
    column = _TOPIC_OF[str(entry["tbl"])]
    if column is None:
        return int(entry["row"])
    old = _old(entry).get(column)
    if old is not None:
        return int(old)
    now = conn.execute(
        f'SELECT "{column}" FROM "{entry["tbl"]}" WHERE rowid = ?',  # noqa: S608
        (entry["row"],),
    ).fetchone()
    return int(now[0]) if now else None


def _is_file(conn: sqlite3.Connection, entry: sqlite3.Row) -> bool:
    """A section of a source, not one of a brief's own (source ``node-N``)."""
    kind = _old(entry).get("source_type")
    if kind is None:
        row = conn.execute(
            "SELECT source_type FROM sections WHERE rowid = ?", (entry["row"],)
        ).fetchone()
        kind = row[0] if row else None
    return kind is not None and str(kind).strip("'") != "node"


def _old(entry: sqlite3.Row) -> dict[str, object]:
    """The row's old values, as plain values (``quote()`` literals undone)."""
    if not entry["before"]:
        return {}
    return {
        column: _plain(literal)
        for column, literal in json.loads(entry["before"]).items()
    }


def _plain(literal: str) -> object:
    if literal == "NULL":
        return None
    if literal.startswith("'"):
        return literal[1:-1].replace("''", "'")
    try:
        return int(literal)
    except ValueError:
        return literal
