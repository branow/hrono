"""What a topic is called, wherever it is shown (#156, #103, #212).

ONE rule, so the map, the side panel, the topic page, the Ask page and the
exported folder an agent reads all call a topic the same thing: the name a
person gave it, else a short title taken from its brief.

Where a topic's files live used to be its name on the map (#198), because a
weak model opened every brief with the same clause — and the review tree then
had four siblings called ``src/click``, which is the one thing siblings share.
Where it lives is now the second line; this is the first. Two siblings must
still never read the same, so a title shared under one parent carries the
topic's number, the one thing that is certainly different.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable

from hrono.summarize import briefs


def names(conn: sqlite3.Connection, node_ids: Iterable[int]) -> dict[int, str]:
    """The display name of each topic, told apart from its siblings.

    Siblings are the children of the same stored parent (topics with none are
    siblings of each other within their tree), so the answer for a topic does
    not depend on which page asked or what else that page shows.
    """
    wanted = sorted(set(node_ids))
    if not wanted:
        return {}
    named: dict[int, str] = {}
    for group in _families(conn, wanted):
        titles = {node: heading(conn, node) for node in group}
        counts: dict[str, int] = {}
        for title in titles.values():
            counts[title.casefold()] = counts.get(title.casefold(), 0) + 1
        for node in group:
            if node in wanted:
                title = titles[node]
                shared = counts[title.casefold()] > 1
                named[node] = f"{title} (#{node})" if shared else title
    return named


def name(conn: sqlite3.Connection, node_id: int) -> str:
    """One topic's display name (``names`` for a single topic)."""
    return names(conn, [node_id]).get(node_id, f"topic {node_id}")


def _families(conn: sqlite3.Connection, wanted: list[int]) -> list[list[int]]:
    """Each wanted topic's sibling group, every sibling included."""
    marks = ",".join("?" * len(wanted))
    rows = conn.execute(
        "SELECT n.id AS id, n.tree AS tree, c.parent_id AS parent "  # noqa: S608
        "FROM nodes n LEFT JOIN node_children c ON c.child_id = n.id "
        f"WHERE n.id IN ({marks})",
        wanted,
    ).fetchall()
    groups: dict[tuple[str, int | None], list[int]] = {}
    for row in rows:
        key = (str(row["tree"]), row["parent"])
        if key in groups:
            continue
        groups[key] = _siblings(conn, key[0], key[1])
    return list(groups.values())


def _siblings(
    conn: sqlite3.Connection, tree: str, parent: int | None
) -> list[int]:
    if parent is not None:
        rows = conn.execute(
            "SELECT child_id AS id FROM node_children WHERE parent_id = ? "
            "ORDER BY child_id",
            (parent,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT n.id AS id FROM nodes n WHERE n.tree = ? AND NOT EXISTS "
            "(SELECT 1 FROM node_children c WHERE c.child_id = n.id) "
            "ORDER BY n.id",
            (tree,),
        ).fetchall()
    return [int(row["id"]) for row in rows]


def heading(conn: sqlite3.Connection, node_id: int) -> str:
    """A short title for a node: the operator's if they named it (#156).

    A stored title wins outright. Deriving one from the brief is the default,
    not the rule, and a human who renamed a topic has said something the model
    cannot: what the topic is FOR in this organisation.

    The brief's SHAPE used to leak into navigation (#103): a brief opening with
    a generic ``## Summary`` heading named its export directory ``summary-2``,
    and one opening with a paragraph made the whole paragraph a link title. The
    brief is not at fault for either — a heading is a reasonable way to start a
    summary — so the fix is here rather than a shape rule that would retry and
    flag a perfectly good brief. A boilerplate heading is skipped, markdown
    emphasis is dropped, and only the first sentence is kept.
    """
    stored = _stored_title(conn, node_id)
    if stored:
        return stored
    for line in _brief_text(conn, node_id).strip().splitlines():
        found = title(line)
        if found and slug(found) not in _BOILERPLATE:
            return found
    return f"topic {node_id}"


def _brief_text(conn: sqlite3.Connection, node_id: int) -> str:
    row = briefs.get(conn, node_id)
    return row["text"] if row is not None else ""


def _stored_title(conn: sqlite3.Connection, node_id: int) -> str | None:
    row = conn.execute(
        "SELECT title FROM nodes WHERE id = ?", (node_id,)
    ).fetchone()
    if row is None:
        return None
    title = row["title"]
    return str(title).strip() or None if title else None


def title(line: str) -> str:
    """The first sentence of ``line``, cut to a title's length at a word."""
    return sentence(line, _TITLE_CHARS)


def sentence(line: str, limit: int) -> str:
    """The first sentence of ``line``, emphasis dropped, cut at a word."""
    text = _EMPHASIS.sub("", line.lstrip("#").strip())
    first = re.split(r"(?<=[.!?])\s", text, maxsplit=1)[0].strip()
    if len(first) <= limit:
        return first
    # whole words, and SAY it was cut: a heading that stops mid-clause reads
    # as a rendering fault rather than as a title someone abbreviated
    return first[:limit].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def slug(text: str) -> str:
    """A name as a path segment: lowercase words joined by dashes."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


_TITLE_CHARS = 80
_EMPHASIS = re.compile(r"[*_`]+")
_BOILERPLATE = frozenset(
    {
        "summary",
        "overview",
        "brief",
        "introduction",
        "intro",
        "description",
        "topic",
        "abstract",
        "contents",
        "notes",
    }
)
