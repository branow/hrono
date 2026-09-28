"""One topic, read beside the map rather than instead of it (#199).

Clicking a topic used to leave the map for the topic page, which throws away
the thing the click was asking a question about — where that topic sits. The
map answers it in place instead: `?focus=<id>` renders this panel next to the
canvas, and the canvas stays exactly as it was drawn.

What the panel holds is deliberately the READING half of the topic page: its
place, its brief, what it is made of. Every control that CHANGES a topic stays
on the topic page, which the panel links to — two copies of a form are two
places a permission rule can drift apart, and the edits are admin-gated where
they already live.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from hrono.server import where as where_module
from hrono.summarize import briefs

# Enough of a section to recognise which one it is, in a column a third of the
# page wide. The topic page is where a section is actually read.
PREVIEW_CHARS = 220


@dataclass(frozen=True)
class Part:
    """One thing a topic is made of: a section it holds, or a topic under it."""

    id: int
    name: str
    detail: str


@dataclass(frozen=True)
class Panel:
    """A topic as the map shows it beside itself."""

    id: int
    level: int
    where: str
    spread: str
    title: str
    brief: str
    stale: bool
    holds: int
    holds_what: str
    parts: tuple[Part, ...]


def build(conn: sqlite3.Connection, tree: str, node_id: int) -> Panel | None:
    """The focused topic, or None when `?focus=` names nothing in this tree.

    None rather than a 404: the focus is a VIEW of the map, and a view cannot
    be invalid — a stale link should draw the map without a panel, never an
    error page over the map it was pointing at.
    """
    row = conn.execute(
        "SELECT id, level, title FROM nodes WHERE tree = ? AND id = ?",
        (tree, node_id),
    ).fetchone()
    if row is None:
        return None
    place = where_module.describe(conn, tree).get(
        node_id, where_module.Where("", "")
    )
    brief = briefs.get(conn, node_id)
    sections = _sections(conn, node_id, place.label)
    children = _children(conn, tree, node_id)
    return Panel(
        id=node_id,
        level=int(row["level"]),
        where=place.label,
        spread=place.spread,
        # only a name someone GAVE it. The map falls back to the brief's first
        # line, which here would print the brief's opening twice in a column
        # two inches wide — the brief itself is three lines further down
        title=str(row["title"] or ""),
        brief="" if brief is None else str(brief["text"]),
        # the same rule the map colours by: no brief counts as a stale one,
        # because both mean recall cannot answer from this topic
        stale=brief is None or bool(brief["stale"]),
        holds=len(sections) or len(children),
        holds_what="sections" if sections else "topics",
        parts=sections or children,
    )


def _sections(
    conn: sqlite3.Connection, node_id: int, stem: str
) -> tuple[Part, ...]:
    """A topic's sections, WORST FIT FIRST.

    `assignment_similarity` is the score a section was attached with, and NULL
    means a confident density-core placement (0009_nodes.sql) — so nulls sort
    LAST, not first. Someone opening a topic to see whether it is right wants
    the section least likely to belong at the top.
    """
    return tuple(
        Part(
            id=int(row["id"]),
            name=_relative(str(row["path"]), stem),
            detail=_preview(row["body"]),
        )
        for row in conn.execute(
            "SELECT s.id AS id, s.path AS path, c.body AS body "
            "FROM node_members m JOIN sections s ON s.id = m.section_id "
            "LEFT JOIN contents c ON c.content_hash = s.content_hash "
            "WHERE m.node_id = ? "
            "ORDER BY m.assignment_similarity IS NULL, "
            "m.assignment_similarity, s.id",
            (node_id,),
        ).fetchall()
    )


def _children(
    conn: sqlite3.Connection, tree: str, node_id: int
) -> tuple[Part, ...]:
    """The topics under this one, named the way the map names them."""
    wheres = where_module.by_node(conn, tree)
    return tuple(
        Part(
            id=int(row["child_id"]),
            name=wheres.get(int(row["child_id"]), "") or "unplaced",
            detail=f"{int(row['members']) or int(row['kids'])} "
            f"{'sections' if int(row['members']) else 'topics'}",
        )
        for row in conn.execute(
            "SELECT c.child_id AS child_id, "
            "(SELECT COUNT(*) FROM node_members m WHERE m.node_id = c.child_id)"
            " AS members, "
            "(SELECT COUNT(*) FROM node_children k "
            "WHERE k.parent_id = c.child_id) AS kids "
            "FROM node_children c WHERE c.parent_id = ? ORDER BY c.child_id",
            (node_id,),
        ).fetchall()
    )


def _relative(path: str, stem: str) -> str:
    """A section's path with the directory its whole topic shares taken off.

    Thirty rows opening with the same twenty characters are thirty rows nobody
    scans (#198). The shared head is on the panel already, as the topic's own
    name.
    """
    return path.removeprefix(f"{stem}/") if stem else path


def _preview(body: object) -> str:
    if body is None:
        return "(content not stored)"
    text = bytes(body).decode("utf-8", "replace").strip()
    return text[:PREVIEW_CHARS] + ("…" if len(text) > PREVIEW_CHARS else "")
