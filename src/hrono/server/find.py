"""Finding things on the map without walking it.

The map is one way in, and a person who knows a word, a file or a topic's
shape should not have to expand circles to reach it. Three reads over what the
tree already stores, none of them a second index:

- ``search`` asks the FTS5 index recall keeps (``passages_fts``) — which holds
  every section's path and text AND every brief, because a brief is stored as
  passages too — plus the names a person gave topics, which are not in it.
  Words, not meaning: a question belongs to Ask.
- ``outline`` is the tree as a nested list, the same topics the map draws with
  the same names and the same health rule, for the people who read lists and
  for a tree too big to draw.
- ``lookup`` goes from a file path or a directory to the sections cut from it
  and the topic each one was filed under.

Every read is scoped to one tree: a section is "in" a tree when a topic of it
holds the section or its pending pool does.
"""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

from markupsafe import Markup, escape

from hrono import naming
from hrono.cluster import incubator
from hrono.registry.collections import trees
from hrono.server import triage
from hrono.server import where as where_module

# Enough candidate passages that a section-heavy word cannot crowd the briefs
# out, few enough that one request stays a fraction of a second.
CANDIDATES = 300
SHOWN = 25
# FTS5 marks the matched words; these two never occur in text, so they survive
# the escaping that makes the snippet safe to put in a page.
_OPEN, _CLOSE = "\x02", "\x03"
_WORD = re.compile(r"\w+")
MAX_TERMS = 8


@dataclass(frozen=True)
class Topic:
    id: int
    name: str
    where: str
    why: str  # "named" (a person's title) or "brief"
    snippet: Markup


@dataclass(frozen=True)
class Section:
    id: int
    path: str
    source: str
    version: str
    topic: int | None  # None: parked, or in no topic of this tree
    topic_name: str
    parked: bool
    snippet: Markup


@dataclass(frozen=True)
class Found:
    topics: tuple[Topic, ...]
    sections: tuple[Section, ...]
    more: bool  # there were more matches than are shown


def search(conn: sqlite3.Connection, tree: str, query: str) -> Found:
    """Topics and sections of ``tree`` containing every word of ``query``."""
    terms = _terms(query)
    if not terms:
        return Found((), (), False)
    written = _matches(conn, tree, terms, _BRIEFS)
    cited = _matches(conn, tree, terms, _SECTIONS)
    named = _titled(conn, tree, terms)
    seen_topics: set[int] = set(named)
    topic_hits: list[tuple[int, Markup, str]] = [
        (node, Markup(""), "named") for node in named
    ]
    seen_sections: set[int] = set()
    section_hits: list[sqlite3.Row] = []
    for row in (*written, *cited):
        if row["source_type"] == "node":
            node = int(str(row["source"]).removeprefix("node-"))
            if node not in seen_topics:
                seen_topics.add(node)
                topic_hits.append((node, _marked(row["snip"]), "brief"))
        elif int(row["section_id"]) not in seen_sections:
            seen_sections.add(int(row["section_id"]))
            section_hits.append(row)
    more = CANDIDATES in (len(written), len(cited)) or (
        len(topic_hits) > SHOWN or len(section_hits) > SHOWN
    )
    topic_hits = topic_hits[:SHOWN]
    section_hits = section_hits[:SHOWN]
    homes = _homes(conn, tree, [int(row["section_id"]) for row in section_hits])
    called = naming.names(
        conn, [node for node, _, _ in topic_hits] + list(homes.values())
    )
    wheres = where_module.by_node(conn, tree)
    return Found(
        topics=tuple(
            Topic(
                node,
                called.get(node, f"topic {node}"),
                wheres.get(node, ""),
                why,
                snip,
            )
            for node, snip, why in topic_hits
        ),
        sections=tuple(
            _section(row, homes.get(int(row["section_id"])), called, tree, conn)
            for row in section_hits
        ),
        more=more,
    )


def _terms(query: str) -> tuple[str, ...]:
    seen = dict.fromkeys(term.lower() for term in _WORD.findall(query))
    return tuple(seen)[:MAX_TERMS]


# The two kinds of passage are searched separately: a section-heavy word would
# otherwise fill every candidate slot and a brief that matches never be seen.
_BRIEFS = (
    "p.source_type = 'node' AND CAST(substr(p.source, 6) AS INTEGER) "
    "IN (SELECT id FROM nodes WHERE tree = :tree)"
)
_SECTIONS = (
    "p.source_type != 'node' AND ("
    "EXISTS (SELECT 1 FROM node_members m JOIN nodes n "
    "ON n.id = m.node_id WHERE m.section_id = p.section_id "
    "AND n.tree = :tree) "
    "OR EXISTS (SELECT 1 FROM pending q WHERE q.section_id = p.section_id "
    "AND q.tree = :tree))"
)


def _matches(
    conn: sqlite3.Connection, tree: str, terms: tuple[str, ...], scope: str
) -> list[sqlite3.Row]:
    """The best passages containing every term (a word, or its prefix)."""
    match = " ".join(f'"{term}"*' for term in terms)
    return conn.execute(
        "SELECT p.section_id AS section_id, p.source AS source, "  # noqa: S608
        "p.source_type AS source_type, s.path AS path, s.source AS origin, "
        "s.version AS version, "
        f"snippet(passages_fts, 1, '{_OPEN}', '{_CLOSE}', '…', 24) AS snip "
        "FROM passages_fts f JOIN passages p ON p.id = f.passage_id "
        "JOIN sections s ON s.id = p.section_id "
        f"WHERE passages_fts MATCH :match AND ({scope}) "
        "ORDER BY bm25(passages_fts) LIMIT :limit",
        {"match": match, "tree": tree, "limit": CANDIDATES},
    ).fetchall()


def _titled(
    conn: sqlite3.Connection, tree: str, terms: tuple[str, ...]
) -> list[int]:
    """Topics a person named: no passage holds a title, so ask for it."""
    clause = " AND ".join("lower(title) LIKE ? ESCAPE '\\'" for _ in terms)
    rows = conn.execute(
        "SELECT id FROM nodes WHERE tree = ? AND "  # noqa: S608
        f"{clause} ORDER BY id",
        (tree, *(f"%{_like(term)}%" for term in terms)),
    ).fetchall()
    return [int(row["id"]) for row in rows]


def _homes(
    conn: sqlite3.Connection, tree: str, sections: list[int]
) -> dict[int, int]:
    """Each section's topic in this tree; a parked or unfiled one has none."""
    if not sections:
        return {}
    marks = ",".join("?" * len(sections))
    rows = conn.execute(
        "SELECT m.section_id AS section_id, MIN(m.node_id) AS node "  # noqa: S608
        "FROM node_members m JOIN nodes n ON n.id = m.node_id "
        f"WHERE n.tree = ? AND m.section_id IN ({marks}) "
        "GROUP BY m.section_id",
        (tree, *sections),
    ).fetchall()
    return {int(row["section_id"]): int(row["node"]) for row in rows}


def _section(
    row: sqlite3.Row,
    home: int | None,
    called: dict[int, str],
    tree: str,
    conn: sqlite3.Connection,
) -> Section:
    section = int(row["section_id"])
    return Section(
        id=section,
        path=str(row["path"]),
        source=str(row["origin"]),
        version=str(row["version"])[:12],
        topic=home,
        topic_name="" if home is None else called.get(home, f"topic {home}"),
        parked=home is None
        and incubator.parked_batch(conn, tree, section) is not None,
        snippet=_marked(row["snip"]),
    )


def _marked(snippet: str) -> Markup:
    """A snippet with its matched words in ``<mark>``, the rest escaped."""
    text = str(escape(snippet))
    return Markup(text.replace(_OPEN, "<mark>").replace(_CLOSE, "</mark>"))


def _like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# -- the outline -----------------------------------------------------------


@dataclass(frozen=True)
class Row:
    """One topic in the outline, and the topics under it."""

    id: int
    name: str
    where: str
    holds: int  # members for a leaf, children for an upper topic
    holds_what: str
    sections: int  # sections anywhere beneath it
    healthy: bool
    kids: tuple[Row, ...]


def outline(conn: sqlite3.Connection, tree: str) -> tuple[Row, ...]:
    """The whole tree, top-down, in the order the map lays siblings."""
    nodes = [
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ? ORDER BY id", (tree,)
        ).fetchall()
    ]
    if not nodes:
        return ()
    children = _kids(conn, tree)
    members = _member_counts(conn, tree)
    unwell = set(triage.unanswerable(conn, tree))
    called = naming.names(conn, nodes)
    wheres = where_module.by_node(conn, tree)
    below = {child for kids in children.values() for child in kids}

    def build(node: int) -> Row:
        kids = tuple(build(kid) for kid in children.get(node, ()))
        own = members.get(node, 0)
        return Row(
            id=node,
            name=called[node],
            where=wheres.get(node, ""),
            holds=len(kids) or own,
            holds_what="topics" if kids else "sections",
            sections=own + sum(kid.sections for kid in kids),
            healthy=node not in unwell,
            kids=kids,
        )

    return tuple(build(node) for node in nodes if node not in below)


def _kids(conn: sqlite3.Connection, tree: str) -> dict[int, list[int]]:
    edges: dict[int, list[int]] = {}
    for row in conn.execute(
        "SELECT c.parent_id AS parent, c.child_id AS child "
        "FROM node_children c JOIN nodes n ON n.id = c.parent_id "
        "WHERE n.tree = ? ORDER BY c.child_id",
        (tree,),
    ).fetchall():
        edges.setdefault(int(row["parent"]), []).append(int(row["child"]))
    return edges


def _member_counts(conn: sqlite3.Connection, tree: str) -> dict[int, int]:
    return {
        int(row["node"]): int(row["n"])
        for row in conn.execute(
            "SELECT m.node_id AS node, COUNT(*) AS n FROM node_members m "
            "JOIN nodes n ON n.id = m.node_id WHERE n.tree = ? "
            "GROUP BY m.node_id",
            (tree,),
        ).fetchall()
    }


# -- file lookup -----------------------------------------------------------


@dataclass(frozen=True)
class Placed:
    """A section of a file, and where the tree filed it."""

    id: int
    ordinal: int
    start: int
    end: int
    version: str
    topic: int | None
    topic_name: str
    parked: bool


@dataclass(frozen=True)
class File:
    path: str
    source: str
    sections: tuple[Placed, ...]


@dataclass(frozen=True)
class Located:
    """What a path or prefix names. ``files`` empty means not ingested."""

    path: str
    files: tuple[File, ...]
    more: int  # files beyond those shown


FILES_SHOWN = 40


def lookup(conn: sqlite3.Connection, tree: str, path: str) -> Located:
    """The sections cut from ``path`` (a file) or under it (a directory)."""
    wanted = path.strip().removeprefix("./").lstrip("/")
    if not wanted:
        return Located("", (), 0)
    mine = trees.scoped_sources(conn, tree)
    named = {f"s{i}": name for i, name in enumerate(mine)}
    # A section belongs to this tree by its source, or by being filed or
    # pending in it; another tree's source sharing a path is not this tree's.
    rows = conn.execute(
        "SELECT id, source, path, version, ordinal, byte_start, byte_end "  # noqa: S608
        "FROM sections WHERE source_type != 'node' AND "
        "(path = :path OR path LIKE :prefix ESCAPE '\\') AND ("
        f"source IN ({', '.join(f':{key}' for key in named) or 'NULL'}) "
        "OR EXISTS (SELECT 1 FROM node_members m JOIN nodes n "
        "ON n.id = m.node_id WHERE m.section_id = sections.id "
        "AND n.tree = :tree) "
        "OR EXISTS (SELECT 1 FROM pending q WHERE q.section_id = sections.id "
        "AND q.tree = :tree)) ORDER BY path, source, ordinal",
        {"path": wanted, "prefix": f"{_like(wanted)}%", "tree": tree, **named},
    ).fetchall()
    keys = list(dict.fromkeys((row["source"], row["path"]) for row in rows))
    shown = set(keys[:FILES_SHOWN])
    kept = [row for row in rows if (row["source"], row["path"]) in shown]
    homes = _homes(conn, tree, [int(row["id"]) for row in kept])
    called = naming.names(conn, list(homes.values()))
    files: dict[tuple[str, str], list[Placed]] = {
        key: [] for key in keys[:FILES_SHOWN]
    }
    for row in kept:
        home = homes.get(int(row["id"]))
        files[(row["source"], row["path"])].append(
            Placed(
                id=int(row["id"]),
                ordinal=int(row["ordinal"]),
                start=int(row["byte_start"]),
                end=int(row["byte_end"]),
                version=str(row["version"])[:12],
                topic=home,
                topic_name="" if home is None else called[home],
                parked=home is None
                and incubator.parked_batch(conn, tree, int(row["id"]))
                is not None,
            )
        )
    return Located(
        path=wanted,
        files=tuple(
            File(path=path_, source=source, sections=tuple(placed))
            for (source, path_), placed in files.items()
        ),
        more=max(0, len(keys) - FILES_SHOWN),
    )
