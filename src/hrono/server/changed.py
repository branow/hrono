"""What one run changed in its tree, read from the change journal.

The run page shows it so a sync can be seen to be incremental and to be
explained: which files changed and how (a diff of the sections that were
cut again), which topics that touched out of how many, and for each topic
why: the sections that came in or left, what the judge said, and its brief
before and after. It is read from ``changes`` (``db/journal.py``), the same
record a revert undoes, so what the page says the run did is what reverting
it takes back.

Old rows are read from the journal's copies; contents are never journaled
(they are keyed by hash and never removed), so an old section's text is
still there to diff against.
"""

from __future__ import annotations

import difflib
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field

from hrono.db import journal
from hrono.naming import names
from hrono.server.i18n import gettext as _
from hrono.summarize import briefs

# What a topic went through, strongest first: a topic both made and
# rewritten in one run is shown as new.
NEW, RETIRED, REWRITTEN, REGROUPED = "new", "retired", "rewritten", "regrouped"
_RANK = {NEW: 0, RETIRED: 1, REWRITTEN: 2, REGROUPED: 3}

DIFF_LINES = 400  # a diff longer than this is cut; the page is not an editor

# A lifecycle decision (``update_log``) in words: (verdict, action) -> why.
_DECIDED = {
    ("home", "forced"): "a new section had no close topic and joined its "
    "nearest one here",
    ("drain", "forced"): "sections waiting for a topic were placed here",
    ("unparseable", "abstained"): "the judge's answer could not be read, so "
    "nothing above was marked",
}


@dataclass(frozen=True)
class Line:
    """One line of a diff: '+' added, '-' removed, ' ' kept, '@' a gap."""

    kind: str
    text: str


@dataclass(frozen=True)
class FileChange:
    """A source file whose sections the run cut again."""

    source: str
    path: str
    status: str  # added, changed, removed
    plus: int
    minus: int
    diff: tuple[Line, ...]

    @property
    def anchor(self) -> str:
        return anchor(self.path)


def anchor(path: str) -> str:
    """The id a file's diff has on the page, for a topic to link to."""
    return "file-" + "".join(c if c.isalnum() else "-" for c in path)


@dataclass
class TopicChange:
    """What happened to one topic, and why."""

    id: int
    what: str
    entered: list[str] = field(default_factory=list)  # files of sections in
    left: list[str] = field(default_factory=list)  # files of sections out
    decided: list[str] = field(default_factory=list)  # the decisions, in words
    below: list[int] = field(default_factory=list)  # changed topics beneath
    before: str | None = None  # its brief before the run
    after: str | None = None  # and after

    @property
    def brief(self) -> tuple[Line, ...]:
        if self.before is None or self.after is None:
            return ()
        return diff(self.before, self.after)


@dataclass(frozen=True)
class Shown:
    """One row of the touched part of the tree, in outline order."""

    id: int
    name: str
    depth: int
    change: TopicChange | None
    unchanged: int  # children of it that the run did not touch, not drawn


@dataclass(frozen=True)
class Changed:
    """One run's changes, as the run page shows them."""

    run: str
    tree: str
    total: int  # the topics the tree has now
    topics: dict[int, TopicChange]
    files: tuple[FileChange, ...]
    outline: tuple[Shown, ...]
    rows: int
    reverted: str | None
    blocker: str | None
    names: dict[int, str]

    def count(self, what: str) -> int:
        return sum(1 for t in self.topics.values() if t.what == what)

    def anchor(self, path: str) -> str:
        return anchor(path)


def changed(conn: sqlite3.Connection, run: str, tree: str) -> Changed | None:
    """What ``run`` changed in ``tree``; None when it changed nothing."""
    entries = conn.execute(
        "SELECT tbl, op, row, before FROM changes WHERE run = ? ORDER BY id",
        (run,),
    ).fetchall()
    if not entries:
        return None
    reverted = conn.execute(
        "SELECT reverted_at FROM reverts WHERE run = ?", (run,)
    ).fetchone()
    total = conn.execute(
        "SELECT COUNT(*) FROM nodes WHERE tree = ?", (tree,)
    ).fetchone()[0]
    sections = _sections(conn, entries)
    topics = _topics(conn, entries, sections)
    alive = [
        int(row[0])
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ?", (tree,)
        ).fetchall()
        if int(row[0]) in topics
    ]
    return Changed(
        run=run,
        tree=tree,
        total=int(total),
        topics=topics,
        files=_files(conn, sections),
        outline=() if reverted else _outline(conn, tree, topics),
        rows=len(entries),
        reverted=str(reverted[0]) if reverted else None,
        blocker=None if reverted else _why(journal.blocker(conn, run)),
        names=names(conn, alive),
    )


@dataclass(frozen=True)
class _Section:
    source: str
    path: str
    content_hash: str
    start: int
    born: bool  # inserted by the run (else deleted by it)


def _sections(
    conn: sqlite3.Connection, entries: list[sqlite3.Row]
) -> dict[int, _Section]:
    """The source sections the run made or removed, by id."""
    found: dict[int, _Section] = {}
    for entry in entries:
        if entry["tbl"] != "sections" or entry["op"] == "update":
            continue
        row = int(entry["row"])
        if entry["op"] == "delete":
            old = _old(entry)
            if row in found:  # made and removed in the same run
                del found[row]
            elif old.get("source_type") != "node":
                found[row] = _Section(
                    str(old["source"]),
                    str(old["path"]),
                    str(old["content_hash"]),
                    int(old["byte_start"]),  # type: ignore[arg-type]
                    born=False,
                )
            continue
        now = conn.execute(
            "SELECT source, source_type, path, content_hash, byte_start "
            "FROM sections WHERE id = ?",
            (row,),
        ).fetchone()
        if now is not None and now["source_type"] != "node":
            found[row] = _Section(
                now["source"],
                now["path"],
                now["content_hash"],
                int(now["byte_start"]),
                born=True,
            )
    return found


def _files(
    conn: sqlite3.Connection, sections: dict[int, _Section]
) -> tuple[FileChange, ...]:
    """Each file the run cut again, with the diff of its cut sections."""
    grouped: dict[tuple[str, str], list[_Section]] = defaultdict(list)
    for section in sections.values():
        grouped[(section.source, section.path)].append(section)
    made = []
    for (source, path), parts in sorted(grouped.items()):
        old = _text(conn, [p for p in parts if not p.born])
        new = _text(conn, [p for p in parts if p.born])
        lines = diff(old, new)
        status = "added" if not old else "removed" if not new else "changed"
        made.append(
            FileChange(
                source=source,
                path=path,
                status=status,
                plus=sum(line.kind == "+" for line in lines),
                minus=sum(line.kind == "-" for line in lines),
                diff=lines,
            )
        )
    return tuple(made)


def _text(conn: sqlite3.Connection, parts: list[_Section]) -> str:
    chunks = []
    for part in sorted(parts, key=lambda p: p.start):
        row = conn.execute(
            "SELECT body FROM contents WHERE content_hash = ?",
            (part.content_hash,),
        ).fetchone()
        if row is not None:
            chunks.append(bytes(row["body"]).decode("utf-8", "replace"))
    return "".join(chunks)


def diff(old: str, new: str) -> tuple[Line, ...]:
    """A unified diff of two texts, as lines the page colours."""
    lines: list[Line] = []
    for said in difflib.unified_diff(
        old.splitlines(), new.splitlines(), n=2, lineterm=""
    ):
        if said.startswith(("---", "+++")):
            continue
        kind = "@" if said.startswith("@@") else said[:1] or " "
        lines.append(Line(kind, said if kind == "@" else said[1:]))
        if len(lines) >= DIFF_LINES:
            lines.append(Line("@", _("… cut")))
            break
    return tuple(lines)


def _topics(
    conn: sqlite3.Connection,
    entries: list[sqlite3.Row],
    sections: dict[int, _Section],
) -> dict[int, TopicChange]:
    topics: dict[int, TopicChange] = {}

    def touch(node: int, what: str) -> TopicChange:
        topic = topics.get(node)
        if topic is None:
            topic = topics[node] = TopicChange(node, what)
        elif _RANK[what] < _RANK[topic.what]:
            topic.what = what
        return topic

    for entry in entries:
        table, op = str(entry["tbl"]), str(entry["op"])
        if table == "nodes":
            what = {"insert": NEW, "delete": RETIRED}.get(op, REGROUPED)
            touch(int(entry["row"]), what)
        elif table == "briefs":
            topic = touch(int(entry["row"]), REWRITTEN)
            if op != "insert" and topic.before is None:
                topic.before = str(_old(entry).get("text") or "")
        elif table == "node_members":
            row = _row(conn, entry, "node_members", "node_id, section_id")
            if row is None:
                continue
            topic = touch(int(row["node_id"]), REGROUPED)  # type: ignore[arg-type]
            path = _path_of(conn, int(row["section_id"]), sections)  # type: ignore[arg-type]
            into = topic.entered if op == "insert" else topic.left
            if path and path not in into and op != "update":
                into.append(path)
        elif table == "node_children":
            row = _row(conn, entry, "node_children", "parent_id")
            if row is not None:
                touch(int(row["parent_id"]), REGROUPED)  # type: ignore[arg-type]
        elif table == "update_log" and op == "insert":
            row = conn.execute(
                "SELECT node_id, verdict, action, climbed_to FROM update_log "
                "WHERE id = ?",
                (entry["row"],),
            ).fetchone()
            if row is not None and int(row["node_id"]) in topics:
                topics[int(row["node_id"])].decided.append(_said(row))
    for topic in topics.values():
        if topic.what != RETIRED:
            now = briefs.get(conn, topic.id)
            topic.after = None if now is None else str(now["text"])
    _beneath(conn, topics)
    return topics


def _beneath(conn: sqlite3.Connection, topics: dict[int, TopicChange]) -> None:
    """Name, for each changed topic, the changed topics directly under it."""
    marks = ",".join("?" * len(topics))
    for row in conn.execute(
        "SELECT parent_id, child_id FROM node_children "  # noqa: S608
        f"WHERE parent_id IN ({marks}) AND child_id IN ({marks})",
        [*topics, *topics],
    ).fetchall():
        topics[int(row["parent_id"])].below.append(int(row["child_id"]))


def _said(row: sqlite3.Row) -> str:
    verdict, action = str(row["verdict"]), str(row["action"])
    known = _DECIDED.get((verdict, action))
    if known:
        return _(known)
    if action == "skipped":
        return _("the judge read the change and found its brief still holds")
    if action == "propagated":
        if verdict == "minor":
            return _(
                "the judge found the change minor for its brief, so it and the topics above it were marked for a rewrite"  # noqa: E501
            )
        if verdict == "major":
            return _(
                "the judge found the change major for its brief, so it and the topics above it were marked for a rewrite"  # noqa: E501
            )
        return _(
            "the judge found the change {verdict} for its brief, so it and the topics above it were marked for a rewrite",  # noqa: E501
            verdict=verdict,
        )
    return f"{verdict}: {action}"


def _row(
    conn: sqlite3.Connection, entry: sqlite3.Row, table: str, columns: str
) -> dict[str, object] | None:
    """A journaled row's values: its old copy, or the row as it is now."""
    old = _old(entry)
    if old:
        return old
    now = conn.execute(
        f"SELECT {columns} FROM {table} WHERE rowid = ?",  # noqa: S608
        (entry["row"],),
    ).fetchone()
    return dict(now) if now else None


def _path_of(
    conn: sqlite3.Connection, section: int, sections: dict[int, _Section]
) -> str | None:
    if section in sections:
        return sections[section].path
    row = conn.execute(
        "SELECT path, source_type FROM sections WHERE id = ?", (section,)
    ).fetchone()
    return None if row is None or row["source_type"] == "node" else row["path"]


def _outline(
    conn: sqlite3.Connection, tree: str, topics: dict[int, TopicChange]
) -> tuple[Shown, ...]:
    """The touched topics and those above them, as an outline.

    Only the branches the run touched are drawn; each row counts the
    children it left out, so a large tree stays a short list.
    """
    children: dict[int, list[int]] = defaultdict(list)
    parent: dict[int, int] = {}
    for row in conn.execute(
        "SELECT c.parent_id AS p, c.child_id AS c FROM node_children c "
        "JOIN nodes n ON n.id = c.parent_id WHERE n.tree = ? "
        "ORDER BY c.parent_id, c.child_id",
        (tree,),
    ).fetchall():
        children[int(row["p"])].append(int(row["c"]))
        parent[int(row["c"])] = int(row["p"])
    root = conn.execute(
        "SELECT id FROM nodes WHERE tree = ? ORDER BY level DESC, id LIMIT 1",
        (tree,),
    ).fetchone()
    if root is None:
        return ()
    shown = {int(root["id"])}
    for node in topics:
        while node not in shown and (node in parent or node == root["id"]):
            shown.add(node)
            node = parent.get(node, node)
    called = names(conn, sorted(shown))
    rows: list[Shown] = []

    def walk(node: int, depth: int) -> None:
        kids = children.get(node, [])
        drawn = [kid for kid in kids if kid in shown]
        rows.append(
            Shown(
                node,
                called.get(node, _("topic {id}", id=node)),
                depth,
                topics.get(node),
                len(kids) - len(drawn),
            )
        )
        for kid in drawn:
            walk(kid, depth + 1)

    walk(int(root["id"]), 0)
    return tuple(rows)


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
        try:
            return float(literal)
        except ValueError:
            return literal


def _why(reason: str | None) -> str | None:
    """The journal's reason a run cannot be reverted, in the page's language."""
    if reason is None:
        return None
    later = re.fullmatch(
        r"a later run changed the tree since: revert (\S+) first", reason
    )
    if later:
        return _(
            "a later run changed the tree since: revert {run} first",
            run=later.group(1),
        )
    return _(reason)
