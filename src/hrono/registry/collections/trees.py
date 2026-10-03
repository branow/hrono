"""The ``trees`` collection: which sources a tree is the map over (#054).

`hrono tree maintain <name>` has taken the tree as a required argument since
#138, while the build loaded every embedded section regardless — so a second
named tree was a duplicate of the first over the whole corpus, and every
section belonged to both. A tree needs to say what it is a map OF.

It says it by naming SOURCES, not sections: ``sections.source`` already records
the registered source a chunk came from, so the association is declared once
per corpus instead of restamped on every ingest.

A tree with no entry here keeps the old behavior — every embedded section —
which is what makes this collection additive: an existing database contains
exactly what it contained before anyone declares a tree.
"""

from __future__ import annotations

import json
import sqlite3

from pydantic import BaseModel, Field

from hrono.registry import store
from hrono.registry.descriptor import (
    Descriptor,
    RegistryName,
    ValidationContext,
    ValidationFailed,
)


class Tree(BaseModel):
    name: RegistryName = Field(
        title="Name",
        description="What the switcher, recall and the command line call it.",
    )
    sources: list[str] = Field(
        min_length=1,
        title="Sources",
        description=(
            "The registered sources it maps. Only these are clustered into it."
        ),
    )


def _validate(config: dict[str, object], context: ValidationContext) -> None:
    """Reject a tree naming a source that is not registered.

    The same reference check every other collection makes: a tree whose source
    does not exist builds an empty map and reports success, which is the
    failure #132 named — an op that declines work and still says it worked.
    """
    named = [str(name) for name in config.get("sources", ())]
    with context.database.connect() as conn:
        known = {str(row["name"]) for row in store.list_all(conn, "sources")}
    missing = sorted(set(named) - known)
    if missing:
        raise ValidationFailed(
            "tree names unregistered sources: " + ", ".join(missing)
        )


def _before_delete(name: str, context: ValidationContext) -> str | None:
    """Say what deleting a tree's config arms, at the moment it is done.

    An absent row means UNSCOPED, which is the right meaning and the whole
    reason this collection is additive over every database built before it
    (#054) — so the next `maintain` on a tree whose config is gone clusters
    EVERY source in the corpus into it. One small row, a very large operation,
    and nothing said so until it happened (#167).

    Not a refusal: wanting a tree unscoped again is legitimate, and the config
    is one PUT away from coming back. What was missing is that the operator
    hears it.
    """
    with context.database.connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM nodes WHERE tree = ?", (name,)
        ).fetchone()
    built = int(row["n"]) if row is not None else 0
    if built == 0:
        return None
    return (
        f"tree {name} now maps EVERY source: the next maintain will cluster "
        f"the whole corpus into it, over the {built} topic(s) it holds today"
    )


TREES = Descriptor(
    collection="trees",
    model=Tree,
    secret_paths=(),
    write_role="writer",
    validate=_validate,
    before_delete=_before_delete,
)


def sources_of(conn: sqlite3.Connection, tree: str) -> tuple[str, ...] | None:
    """The sources a tree is the map over, or None when it declares no entry.

    None is not "no sources" — it is "unscoped", the behavior every database
    built before this collection existed already has. An entry always names at
    least one source, so an empty tuple never reaches a caller.
    """
    row = store.get(conn, "trees", tree)
    if row is None:
        return None
    return tuple(
        str(name) for name in json.loads(row["config"]).get("sources", ())
    )


def scoped_sources(conn: sqlite3.Connection, tree: str) -> tuple[str, ...]:
    """The registered sources this tree ingests, in registry order.

    Every source when the tree declares no entry, which is the behavior
    `maintain` and `update` had for every tree at once: both iterated the whole
    registry, so `hrono tree sync beta` pulled alpha's sources into beta by the
    incremental door even after the build learned to scope itself.

    Intersected with what is actually registered, so a tree naming a source
    that has since been deleted simply does not ingest it.
    """
    scope = sources_of(conn, tree)
    names = tuple(str(row["name"]) for row in store.list_all(conn, "sources"))
    if scope is None:
        return names
    return tuple(name for name in names if name in scope)
