"""What a topic is ABOUT, taken from the files it holds.

A brief-derived name is only as good as the model that wrote one. On a tree
summarised by a weak model every topic is called "This group covers State,
what…", and twenty-six identical labels are not a map. The files underneath do
not lie: a topic whose sections are all under ``src/hrono/db`` is the database,
whatever its brief says.

So each topic is labelled by the deepest directory that holds MOST of its
sections — not the strict common prefix, which collapses to ``src/hrono`` for
half a repository and distinguishes nothing.

A topic that genuinely straddles the tree is not named by the two SHALLOW roots
it spans, because that puts ``src + tests`` on the root and on the largest topic
— the two a person looks at first, both telling nothing. A straddle is named by
descending INTO each of those two roots as far as each one is itself dominated,
so it reads ``src/hrono + tests``; the shares that make it a straddle are
carried alongside, for the tooltip and the map's panel.

The one root of the tree spans everything by construction, so no directory
dominates it. Saying so — "whole tree" — is true and useless: it is the first
label anyone reads and it names nothing. What the root actually
is, is the SOURCES it was built from, which are named by the operator and are
the one label on the map that needs no explaining: a tree ingested from the
``click`` repository has ``click`` on top.
"""

from __future__ import annotations

import sqlite3
from collections import Counter
from dataclasses import dataclass

# How much of a topic a directory must hold to name it. Below this the topic
# really is spread, and claiming one directory would be a label that lies.
SHARE = 0.6
# Between the two directories a straddling topic is named by. Kept as a
# constant because the map has to recognise it to cut such a label in half
# rather than through one side of it.
STRADDLE = " + "
# Past this many sources, naming them all is a paragraph, not a label.
NAMED_SOURCES = 2


@dataclass(frozen=True)
class Where:
    """A topic's place: what to call it, and how spread it actually is.

    ``spread`` is empty for a topic one directory holds — there is nothing to
    disclose. It is filled only where the label had to name more than one
    place, which is exactly where a reader needs to know the proportions
    before trusting either name.
    """

    label: str
    spread: str


def by_node(conn: sqlite3.Connection, tree: str) -> dict[int, str]:
    """Every topic in the tree, labelled by where its sections live."""
    return {node: place.label for node, place in describe(conn, tree).items()}


def describe(conn: sqlite3.Connection, tree: str) -> dict[int, Where]:
    """Every topic's label and, where it straddles, its shares.

    An upper topic has no sections of its own, so it takes its descendants' —
    which is what lets the top of the map read as a place at all.
    """
    held = _member_dirs(conn, tree)
    children = _children(conn, tree)
    for node in _bottom_up(conn, tree):
        for child in children.get(node, ()):
            held.setdefault(node, []).extend(held.get(child, ()))
    crown = _crown(conn, tree, children)
    top = _sources(conn, tree) if crown is not None else ""
    return {
        node: _place(dirs, top if node == crown else None)
        for node, dirs in held.items()
    }


def _member_dirs(
    conn: sqlite3.Connection, tree: str
) -> dict[int, list[tuple[str, ...]]]:
    """Each leaf topic's sections, as the directories that contain them."""
    held: dict[int, list[tuple[str, ...]]] = {}
    for row in conn.execute(
        "SELECT m.node_id AS node_id, s.path AS path "
        "FROM node_members m "
        "JOIN sections s ON s.id = m.section_id "
        "JOIN nodes n ON n.id = m.node_id "
        "WHERE n.tree = ?",
        (tree,),
    ).fetchall():
        held.setdefault(int(row["node_id"]), []).append(
            tuple(str(row["path"]).split("/")[:-1])
        )
    return held


def _sources(conn: sqlite3.Connection, tree: str) -> str:
    """What the tree was built FROM, as the root's label.

    The operator named these when registering them, so they are the one place
    on the map whose name needs no derivation. Beyond a couple the names stop
    fitting a label and the count is the honest thing to say.
    """
    names = [
        str(row["source"])
        for row in conn.execute(
            "SELECT DISTINCT s.source AS source "
            "FROM node_members m "
            "JOIN sections s ON s.id = m.section_id "
            "JOIN nodes n ON n.id = m.node_id "
            "WHERE n.tree = ? ORDER BY s.source",
            (tree,),
        ).fetchall()
    ]
    if not names:
        return ""
    if len(names) > NAMED_SOURCES:
        return f"{len(names)} sources"
    return STRADDLE.join(names)


def _children(conn: sqlite3.Connection, tree: str) -> dict[int, list[int]]:
    edges: dict[int, list[int]] = {}
    for row in conn.execute(
        "SELECT c.parent_id AS parent, c.child_id AS child "
        "FROM node_children c JOIN nodes n ON n.id = c.parent_id "
        "WHERE n.tree = ?",
        (tree,),
    ).fetchall():
        edges.setdefault(int(row["parent"]), []).append(int(row["child"]))
    return edges


def _crown(
    conn: sqlite3.Connection, tree: str, children: dict[int, list[int]]
) -> int | None:
    """The one topic nothing points at, or None when there is not exactly one.

    The source label is only honest about a single crown. A tree mid-repair
    has several tops, and naming each of them after the whole corpus would
    describe a broken shape as a whole one.
    """
    parented = {child for kids in children.values() for child in kids}
    tops = [node for node in _bottom_up(conn, tree) if node not in parented]
    return tops[0] if len(tops) == 1 else None


def _bottom_up(conn: sqlite3.Connection, tree: str) -> list[int]:
    """Topics from the leaves upwards, so a parent is reached after its kids.

    Level is the tree's own depth counter — 0 at the leaves — so ordering by
    it is the topological order without walking the edges twice.
    """
    return [
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ? ORDER BY level, id",
            (tree,),
        ).fetchall()
    ]


def _place(dirs: list[tuple[str, ...]], crown: str | None) -> Where:
    """Where one topic is. ``crown`` is the root's sources — None if not root.

    The root is only labelled by its sources when no directory dominates it —
    a tree that is all of ``src/hrono`` is better described by that than by
    the name of the repository it came out of. What it must never fall back to
    is the straddle, which on the root is two arbitrary halves of itself.
    """
    deepest = _dominant(dirs)
    if deepest:
        return Where("/".join(deepest), "")
    straddle = _straddled(dirs)
    if crown:
        return Where(crown, straddle.spread)
    return straddle


def _dominant(dirs: list[tuple[str, ...]]) -> tuple[str, ...]:
    """Descend while one directory still holds SHARE of everything."""
    total = len(dirs)
    prefix: tuple[str, ...] = ()
    while True:
        depth = len(prefix)
        deeper = Counter(
            path[: depth + 1]
            for path in dirs
            if len(path) > depth and path[:depth] == prefix
        )
        if not deeper:
            return prefix
        candidate, held = deeper.most_common(1)[0]
        if held < total * SHARE:
            return prefix
        prefix = candidate


def _straddled(dirs: list[tuple[str, ...]]) -> Where:
    """No directory holds it: name the two strongest, each at its own depth.

    Naming the two top-level roots puts ``src + tests`` on half the map.
    A root is the least telling segment of a path, and it is telling precisely
    because the directory UNDER it usually is dominated even when the topic as
    a whole is not — so each side is descended on its own sections.
    """
    roots = Counter(_root_of(path) for path in dirs)
    named = [
        _named(name, held, dirs)
        for name, held in sorted(roots.items(), key=lambda kv: (-kv[1], kv[0]))[
            :2
        ]
    ]
    total = len(dirs) or 1
    return Where(
        label=_both(tuple(name for name, _ in named)),
        spread=", ".join(
            f"{name} {round(100 * held / total)}%" for name, held in named
        ),
    )


def _both(sides: tuple[str, ...]) -> str:
    """Two directories as one label, said the shorter way when they rhyme.

    ``src/hrono/crypto + tests/crypto`` is thirty-one characters in an
    eighteen-character slot, and cut in half it becomes ``…/cryp + …/cry``,
    which names nothing. When both sides end in the same directory that
    directory IS the subject and the roots are what differ, so the label says
    it once: ``crypto: tests+src``.
    """
    tails = {side.rsplit("/", 1)[-1] for side in sides}
    if len(sides) < 2 or len(tails) > 1:
        return STRADDLE.join(sides)
    return f"{tails.pop()}: " + "+".join(
        side.split("/", 1)[0] for side in sides
    )


def _named(
    root: str, held: int, dirs: list[tuple[str, ...]]
) -> tuple[str, int]:
    """One side of a straddle: how deep it is dominated, and how much it is."""
    under = [path for path in dirs if _root_of(path) == root]
    deeper = _dominant(under)
    if not deeper:
        return root, held
    depth = len(deeper)
    return (
        "/".join(deeper),
        sum(1 for path in dirs if path[:depth] == deeper),
    )


def _root_of(path: tuple[str, ...]) -> str:
    """The top segment of a directory, or "/" for a file at the top."""
    return path[0] if path else "/"
