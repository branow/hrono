"""Which passages a tree's recall may answer from (#166).

`POST /trees/<name>/recall` took the tree in its URL and discarded it: both legs
read every passage in the database, so two correctly separated maps still shared
one answer. #054 made that reachable by giving a tree its own sources; this is
the same join on the read door.

The scope is a set of passage ids rather than a SQL predicate threaded into both
legs, because the legs need it BEFORE they compute z — the ruling of 2026-09-25
is that a passage's z is measured against the distribution of the passages that
could have answered, which is this tree's. Filtering afterwards would score
against a population the question was never asked of.

None means unscoped, exactly as ``registry.trees.sources_of`` means it: a tree
with no declared sources searches everything, so a single-corpus database scores
identically to before this existed.
"""

from __future__ import annotations

import sqlite3

from hrono.registry.collections.trees import sources_of


def passages_of(conn: sqlite3.Connection, tree: str) -> frozenset[int] | None:
    """The passage ids this tree may answer from, or None when unscoped.

    Two kinds of passage reach a tree by different routes, and both have to be
    here or recall loses half its corpus:

    - a CONTENT passage through the source it was ingested from, which is the
      join #054 settled;
    - a ``node://`` BRIEF passage (#071) through the tree of the node it
      summarises. A brief has no source of its own — its ``source`` is the
      synthetic ``node-<id>`` — so it is tree-scoped data already, reached
      through ``nodes.tree``.
    """
    sources = sources_of(conn, tree)
    if sources is None:
        return None
    marks = ",".join("?" * len(sources))
    content = conn.execute(
        "SELECT id FROM passages "  # noqa: S608
        f"WHERE source_type != 'node' AND source IN ({marks})",
        tuple(sources),
    ).fetchall()
    briefs = conn.execute(
        "SELECT p.id FROM passages p "
        "JOIN nodes n ON 'node-' || n.id = p.source "
        "WHERE p.source_type = 'node' AND n.tree = ?",
        (tree,),
    ).fetchall()
    return frozenset(int(row["id"]) for row in (*content, *briefs))
