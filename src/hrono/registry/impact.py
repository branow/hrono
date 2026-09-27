"""What a shared-resource edit would do, before it does it (T58, #190).

`sources`, `connections`, `models` and `prompts` are referenced by name from
many trees, so editing one has cross-tree blast radius and `?dry_run=true` is
the spec's safety.

The rule this module lives by: **report what the system actually does, not what
the edit sounds like it should do.** Freshness is decided in ONE place —
`briefs._is_fresh`, reached through `stale_or_missing` — and it compares the
brief's recorded prompt hash and model NAME. So a prompt edit really does
invalidate what that prompt wrote, and a model edit that repoints the row at a
different upstream model really does invalidate nothing. Both are said plainly
here; inventing the second would be a preview that lies in the reassuring
direction.

Numbers nobody measured are never printed. How many SECTIONS a source's new
url yields is not knowable without doing the sync, so it is null with a reason.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from hrono.registry import store
from hrono.registry.trees import sources_of
from hrono.summarize import briefs
from hrono.summarize.resolve import model_fingerprint, template_hash

# Which levels a prompt role governs: `brief` writes level 0, `brief-upper`
# every level above it (`summarize/brief.py`, `summarize/brief_upper.py`).
LEAF_ROLE = "brief"
UPPER_ROLE = "brief-upper"


@dataclass(frozen=True)
class Stale:
    """What would need doing again. ``sections`` is null when unknowable."""

    sections: int | None
    nodes: int
    levels: tuple[int, ...]


@dataclass(frozen=True)
class TreeImpact:
    tree: str
    stale: Stale
    ops: tuple[str, ...]
    reason: str


def preview(
    conn: sqlite3.Connection,
    collection: str,
    name: str,
    proposed: dict[str, object],
) -> tuple[TreeImpact, ...]:
    """The trees this edit would touch, and what it would make stale."""
    current = _current(conn, collection, name)
    if current == proposed:
        return ()
    if collection == "prompts":
        return _prompt_impact(conn, name, current, proposed)
    if collection == "sources":
        return _source_impact(conn, name, current, proposed)
    if collection == "models":
        return _model_impact(conn, name, current, proposed)
    if collection == "connections":
        return _connection_impact(conn, name)
    return ()


def _current(
    conn: sqlite3.Connection, collection: str, name: str
) -> dict[str, object]:
    row = store.get(conn, collection, name)
    return {} if row is None else dict(json.loads(row["config"]))


def _trees(conn: sqlite3.Connection) -> tuple[str, ...]:
    """Every tree that has nodes, plus every tree with a registry row.

    A tree with a config and no nodes yet is still a tree an edit reaches; a
    tree with nodes and no config row is the default one (#054).
    """
    named = {str(row["name"]) for row in store.list_all(conn, "trees")}
    built = {
        str(row["tree"])
        for row in conn.execute("SELECT DISTINCT tree FROM nodes").fetchall()
    }
    return tuple(sorted(named | built))


def _prompt_impact(
    conn: sqlite3.Connection,
    name: str,
    current: dict[str, object],
    proposed: dict[str, object],
) -> tuple[TreeImpact, ...]:
    """A template edit invalidates exactly what that template wrote."""
    role = str(proposed.get("role", current.get("role", "")))
    if proposed.get("template") == current.get("template"):
        return ()
    if role not in (LEAF_ROLE, UPPER_ROLE):
        return tuple(
            TreeImpact(
                tree=tree,
                stale=Stale(sections=0, nodes=0, levels=()),
                ops=(role,) if role else (),
                reason=(
                    f"a {role} prompt edit marks no brief stale: a brief's "
                    f"provenance records its OWN prompt and model, not what "
                    f"produced its inputs"
                ),
            )
            for tree in _trees(conn)
        )
    after = template_hash(str(proposed.get("template", "")))
    before = template_hash(str(current.get("template", "")))
    impacts = []
    for tree in _trees(conn):
        levels = _levels(conn, tree, role)
        newly: list[int] = []
        touched: list[int] = []
        for level, model_name in levels:
            already = set(
                briefs.stale_or_missing(conn, tree, level, before, model_name)
            )
            would = set(
                briefs.stale_or_missing(conn, tree, level, after, model_name)
            )
            fresh_now = would - already
            if fresh_now:
                touched.append(level)
            newly.extend(fresh_now)
        if not newly:
            continue
        impacts.append(
            TreeImpact(
                tree=tree,
                stale=Stale(
                    sections=0, nodes=len(newly), levels=tuple(sorted(touched))
                ),
                ops=("brief",) if role == LEAF_ROLE else ("brief-upper",),
                reason=(
                    "these briefs were written under the old template and the "
                    "next run would rewrite them; nothing re-runs on its own"
                ),
            )
        )
    return tuple(impacts)


def _levels(
    conn: sqlite3.Connection, tree: str, role: str
) -> tuple[tuple[int, str], ...]:
    """The (level, model name) pairs a brief role governs in this tree.

    The model NAME is the one recorded in the briefs at that level, read back
    rather than resolved: the question is what the next run would find stale
    against the model those briefs were written with.
    """
    rows = conn.execute(
        "SELECT DISTINCT n.level AS level, b.model_name AS model "
        "FROM nodes n LEFT JOIN briefs b ON b.node_id = n.id "
        "WHERE n.tree = ? ORDER BY n.level",
        (tree,),
    ).fetchall()
    wanted = [
        (int(row["level"]), str(row["model"]))
        for row in rows
        if row["model"] is not None
        and ((int(row["level"]) == 0) == (role == LEAF_ROLE))
    ]
    return tuple(wanted)


# A source's credential: changing it changes no bytes, so nothing goes stale
# (`implementation-notes.md`). Everything else about a source decides WHAT gets
# pulled, and that is a content change on the next sync.
AUTH_FIELD = "auth"


def _source_impact(
    conn: sqlite3.Connection,
    name: str,
    current: dict[str, object],
    proposed: dict[str, object],
) -> tuple[TreeImpact, ...]:
    if _without_auth(current) == _without_auth(proposed):
        return ()
    return tuple(
        TreeImpact(
            tree=tree,
            stale=Stale(
                sections=None,
                nodes=_holders(conn, tree, name),
                levels=_all_levels(conn, tree),
            ),
            ops=("sync", "cluster", "brief"),
            reason=(
                "this source decides what gets pulled, so the next sync may "
                "change its sections; how many is not knowable without doing "
                "it"
            ),
        )
        for tree in _trees(conn)
        if _in_scope(conn, tree, name)
    )


def _without_auth(config: dict[str, object]) -> dict[str, object]:
    return {k: v for k, v in config.items() if k != AUTH_FIELD}


def _in_scope(conn: sqlite3.Connection, tree: str, source: str) -> bool:
    """Whether this tree pulls from this source (#054): None means all."""
    scope = sources_of(conn, tree)
    return scope is None or source in scope


def _holders(conn: sqlite3.Connection, tree: str, source: str) -> int:
    row = conn.execute(
        "SELECT COUNT(DISTINCT m.node_id) AS n FROM node_members m "
        "JOIN nodes n ON n.id = m.node_id "
        "JOIN sections s ON s.id = m.section_id "
        "WHERE n.tree = ? AND s.source = ?",
        (tree, source),
    ).fetchone()
    return int(row["n"])


def _all_levels(conn: sqlite3.Connection, tree: str) -> tuple[int, ...]:
    """Every level: a leaf change climbs, and the cascade decides where it
    stops at run time (#087), not here."""
    return tuple(
        int(row["level"])
        for row in conn.execute(
            "SELECT DISTINCT level FROM nodes WHERE tree = ? ORDER BY level",
            (tree,),
        ).fetchall()
    )


def _model_impact(
    conn: sqlite3.Connection,
    name: str,
    current: dict[str, object],
    proposed: dict[str, object],
) -> tuple[TreeImpact, ...]:
    """What repointing a model would rewrite.

    Until #191 this was a disclaimer: freshness compared the registry NAME, so
    swapping the upstream model left every brief looking fresh and the preview
    had to say so. It now compares a fingerprint of what decides the WORDS, so
    this is a count — and a credential change still counts nothing, because
    the connection is not part of the fingerprint.
    """
    after = model_fingerprint(proposed)
    if after == model_fingerprint(current):
        return ()
    impacts = []
    for tree in _trees(conn):
        nodes: list[int] = []
        levels: list[int] = []
        for level, model_name in _model_levels(conn, tree, name):
            for prompt_hash in _hashes_at(conn, tree, level):
                already = set(
                    briefs.stale_or_missing(
                        conn, tree, level, prompt_hash, model_name
                    )
                )
                would = set(
                    briefs.stale_or_missing(
                        conn, tree, level, prompt_hash, model_name, after
                    )
                )
                newly = would - already
                if newly:
                    levels.append(level)
                nodes.extend(newly)
        if not nodes:
            continue
        impacts.append(
            TreeImpact(
                tree=tree,
                stale=Stale(
                    sections=0,
                    nodes=len(set(nodes)),
                    levels=tuple(sorted(set(levels))),
                ),
                ops=("brief",),
                reason=(
                    "these briefs were written by the model this name used to "
                    "point at; nothing re-runs on its own"
                ),
            )
        )
    return tuple(impacts)


def _model_levels(
    conn: sqlite3.Connection, tree: str, name: str
) -> tuple[tuple[int, str], ...]:
    """The levels where this model's name is what wrote the briefs."""
    rows = conn.execute(
        "SELECT DISTINCT n.level AS level FROM nodes n "
        "JOIN briefs b ON b.node_id = n.id "
        "WHERE n.tree = ? AND b.model_name = ? ORDER BY n.level",
        (tree, name),
    ).fetchall()
    return tuple((int(row["level"]), name) for row in rows)


def _hashes_at(
    conn: sqlite3.Connection, tree: str, level: int
) -> tuple[str, ...]:
    """The prompt hashes in play at a level.

    `stale_or_missing` asks one (prompt, model) pair at a time, so the model
    question is asked under the prompt those briefs actually carry — otherwise
    the prompt mismatch alone would make everything look stale under both
    hashes and the difference would come back empty.
    """
    rows = conn.execute(
        "SELECT DISTINCT b.prompt_hash AS hash FROM briefs b "
        "JOIN nodes n ON n.id = b.node_id WHERE n.tree = ? AND n.level = ?",
        (tree, level),
    ).fetchall()
    return tuple(str(row["hash"]) for row in rows)


def _writes_briefs(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM briefs WHERE model_name = ?", (name,)
    ).fetchone()
    return int(row["n"]) > 0


def _brief_count(conn: sqlite3.Connection, tree: str, name: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM briefs b JOIN nodes n ON n.id = b.node_id "
        "WHERE n.tree = ? AND b.model_name = ?",
        (tree, name),
    ).fetchone()
    return int(row["n"])


def _connection_impact(
    conn: sqlite3.Connection, name: str
) -> tuple[TreeImpact, ...]:
    """A credential edit changes no output; it can break the models on it."""
    users = [
        str(json.loads(row["config"]).get("name"))
        for row in store.list_all(conn, "models")
        if json.loads(row["config"]).get("connection") == name
    ]
    if not users:
        return ()
    return (
        TreeImpact(
            tree="*",
            stale=Stale(sections=0, nodes=0, levels=()),
            ops=(),
            reason=(
                "nothing goes stale — a connection carries the credential, not "
                f"the words. It is used by: {', '.join(sorted(users))}"
            ),
        ),
    )


def as_json(impacts: Sequence[TreeImpact]) -> dict[str, object]:
    """The response body: `{"affected_trees": [...]}` (the spec's shape)."""
    return {
        "affected_trees": [
            {
                "tree": impact.tree,
                "stale": {
                    "sections": impact.stale.sections,
                    "nodes": impact.stale.nodes,
                    "levels": list(impact.stale.levels),
                },
                "ops": list(impact.ops),
                "reason": impact.reason,
            }
            for impact in impacts
        ]
    }
