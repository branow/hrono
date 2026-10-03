"""The one page where explanation belongs (#197, #200).

Every other page in this dashboard runs to a tight prose budget — a hint on a
mark beside the thing, never a paragraph above it. That rule only works if the
explanation has somewhere to BE, and until now it had nowhere: the vocabulary
lived in a spec outside the repository and in a gitignored working file, so a
person looking at the map could not find out what a topic was without asking.

It reads from the live tree rather than describing a general system: the
numbers in it are this install's, so the pipeline is explained in terms of what
it has actually done here. A guide that describes a general hrono is a guide
whose reader cannot tell which step has not run yet on THEIRS.

What it has to answer, because the map alone does not (#200):

- the SHAPE — not "there is a tree" but how wide each level of this one is
- WHO WRITES WHAT — which configured model is called at which stage
- what the pipeline fixes BY ITSELF, with the numbers it decides on. Without
  this the map's overlays read as a list of errors a person is expected to
  repair by hand, which is the opposite of what they are: they are the residue
  automation looked at and deliberately left alone.
"""

from __future__ import annotations

import json
import sqlite3

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from hrono.cluster.placement import TAU
from hrono.cluster.repair import MAX_CAP, MISFIT_THRESHOLD
from hrono.registry import store
from hrono.server.ui import Reader, _trees, router, templates

# What each configured model role is called FOR, in the order the pipeline
# calls them. The registry stores the role; what the role means is this page's.
ROLES = (
    ("condense", "reads one section and writes what it says"),
    ("brief", "reads a topic's condensations and writes its brief"),
    ("brief-upper", "reads child briefs and writes the brief above them"),
    ("judge", "decides whether a change made a brief wrong"),
    ("embedding", "turns a section into the vector it is placed by"),
)


@router.get("/ui/guide", response_class=HTMLResponse)
def guide_page(request: Request, user: Reader, tree: str = "") -> Response:
    """What hrono is, what it built here, and what every word means."""
    with request.app.state.db.connect() as conn:
        trees = _trees(conn)
        chosen = tree if tree in trees else trees[0]
        stage = _stages(conn, chosen)
        shape = _shape(conn, chosen)
        writers = _writers(conn)
    return templates.TemplateResponse(
        request,
        "guide.html",
        {
            "user": user,
            "trees": trees,
            "tree": chosen,
            "stage": stage,
            "shape": shape,
            "writers": writers,
            "rule": {
                "tau": TAU,
                "cap": MAX_CAP,
                "misfit": int(MISFIT_THRESHOLD * 100),
            },
            "can_write": user.role in {"writer", "admin"},
        },
    )


def _stages(conn: sqlite3.Connection, tree: str) -> dict[str, object]:
    """What this install has at each step of the pipeline.

    A count of zero is as useful as a large one — it says which step has not
    run yet, which is the question somebody reading this page on a half-built
    tree actually has.
    """

    def count(sql: str, *args: object) -> int:
        return int(conn.execute(sql, args).fetchone()[0])

    return {
        "sources": count(
            "SELECT COUNT(*) FROM registry WHERE collection = 'sources'"
        ),
        "sections": count(
            "SELECT COUNT(*) FROM sections WHERE source_type != 'node'"
        ),
        "passages": count("SELECT COUNT(*) FROM passages"),
        "condensations": count("SELECT COUNT(*) FROM condensations"),
        "topics": count("SELECT COUNT(*) FROM nodes WHERE tree = ?", tree),
        "briefs": count(
            "SELECT COUNT(*) FROM briefs b JOIN nodes n ON n.id = b.node_id "
            "WHERE n.tree = ?",
            tree,
        ),
        "levels": count(
            "SELECT COUNT(DISTINCT level) FROM nodes WHERE tree = ?", tree
        ),
        "parked": count("SELECT COUNT(*) FROM pending WHERE tree = ?", tree),
        "stale": count(
            "SELECT COUNT(*) FROM briefs b JOIN nodes n ON n.id = b.node_id "
            "WHERE n.tree = ? AND b.stale = 1",
            tree,
        ),
    }


def _shape(conn: sqlite3.Connection, tree: str) -> list[dict[str, object]]:
    """This tree level by level, widest at the bottom — its actual shape.

    "A tree of topics" is a sentence; "29 topics over 126 sections under one
    root" is the thing itself, and it is the only way a reader can tell a tree
    that built properly from one that collapsed into a single level.
    """
    rows = conn.execute(
        "SELECT n.level AS level, COUNT(*) AS topics, "
        "(SELECT COUNT(*) FROM node_members m "
        " JOIN nodes k ON k.id = m.node_id "
        " WHERE k.tree = n.tree AND k.level = n.level) AS held "
        "FROM nodes n WHERE n.tree = ? GROUP BY n.level ORDER BY n.level DESC",
        (tree,),
    ).fetchall()
    widest = max((int(row["topics"]) for row in rows), default=1)
    return [
        {
            "level": int(row["level"]),
            "topics": int(row["topics"]),
            "held": int(row["held"]),
            # a share, so the template draws a bar without doing arithmetic
            "share": round(100 * int(row["topics"]) / widest),
            "root": int(row["topics"]) == 1 and row is rows[0],
        }
        for row in rows
    ]


def _writers(conn: sqlite3.Connection) -> list[dict[str, str]]:
    """Which configured model is called at each stage, and for what.

    Read from the registry rather than described in general, because "a model
    writes the briefs" is useless next to "cc-brief (sonnet) writes them" when
    the question is why they read the way they do.
    """
    held: dict[str, dict[str, str]] = {}
    for row in store.list_all(conn, "models"):
        config = json.loads(row["config"])
        role = str(config.get("role") or "")
        if config.get("kind") == "embedding":
            role = "embedding"
        if role and role not in held:
            held[role] = {
                "name": str(config.get("name", "")),
                "model": str(config.get("model", "")),
            }
    return [
        {
            "role": role,
            "does": does,
            "name": held.get(role, {}).get("name", ""),
            "model": held.get(role, {}).get("model", ""),
        }
        for role, does in ROLES
    ]
