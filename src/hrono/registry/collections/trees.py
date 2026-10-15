"""The ``trees`` collection: which sources a tree is the map over.

`hrono tree maintain <name>` takes the tree as a required argument, but a build
that loaded every embedded section regardless would make a second named tree a
duplicate of the first over the whole corpus, with every section belonging to
both. A tree needs to say what it is a map OF.

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

from hrono.errors import DomainError
from hrono.registry import store
from hrono.registry.descriptor import (
    Descriptor,
    RegistryName,
    ValidationContext,
    ValidationFailed,
)

DEFAULT_TREE = "default"


class Tree(BaseModel):
    name: RegistryName = Field(
        title="Name",
        description="What the switcher, recall and the command line call it.",
    )
    sources: list[str] = Field(
        min_length=1,
        title="Sources",
        description=(
            "The registered sources it maps. Only these are grouped into it."
        ),
    )
    lookups: bool = Field(
        default=False,
        title="Look into other topics",
        description=(
            "While writing a brief, read the files of the other topics it "
            "sends to or takes from. Briefs say more about how parts fit, at "
            "a few more model calls each."
        ),
    )


def _validate(config: dict[str, object], context: ValidationContext) -> None:
    """Reject a tree naming a source that is not registered or already claimed.

    The reference check is the same one every other collection makes: a tree
    whose source does not exist builds an empty map and reports success, which
    is an op that declines work and still says it worked.

    The CLAIM check is new and load-bearing: ``sections`` has no tree column,
    so a source ingested by two trees is one set of rows both trees mutate.
    Tree A's reconcile drops the rows out of tree B's memberships (the FK
    cascade), and B's next diff sees source-level hashes unchanged and reports
    nothing to do — the sections are gone from B with no record and no error.
    One source therefore belongs to at most one tree, enforced here where the
    overlap is declared rather than at ingest where it is already a corruption.
    """
    name = str(config.get("name", ""))
    named = [str(entry) for entry in config.get("sources", ())]
    with context.database.connect() as conn:
        known = {str(row["name"]) for row in store.list_all(conn, "sources")}
        claims = {
            str(row["name"]): json.loads(row["config"]).get("sources", ())
            for row in store.list_all(conn, "trees")
        }
    missing = sorted(set(named) - known)
    if missing:
        raise ValidationFailed(
            "tree names unregistered sources: " + ", ".join(missing)
        )
    taken = sorted(
        f"{source} (tree {other})"
        for other, sources in claims.items()
        if other != name
        for source in set(named) & {str(entry) for entry in sources}
    )
    if taken:
        raise ValidationFailed(
            "a source belongs to at most one tree; already claimed: "
            + ", ".join(taken)
        )


def _before_delete(name: str, context: ValidationContext) -> str | None:
    """Say what deleting a tree's config arms, at the moment it is done.

    An absent row means UNSCOPED, which is the right meaning and the whole
    reason this collection is additive over every database built before it
    — so the next `maintain` on a tree whose config is gone clusters
    EVERY source in the corpus into it. One small row, a very large operation,
    and nothing would say so until it happened.

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
        f"tree {name} now maps EVERY source: the next maintain will group "
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


def is_known(conn: sqlite3.Connection, tree: str) -> bool:
    """Whether work may be queued for ``tree``: registered, or the default.

    A database nobody has partitioned has exactly one tree, `default`, with no
    registry row; any other name that is not registered is a typo.
    """
    return tree == DEFAULT_TREE or store.get(conn, "trees", tree) is not None


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


def looks_up(conn: sqlite3.Connection, tree: str) -> bool:
    """Whether a tree's leaf briefs are written with lookups."""
    row = store.get(conn, "trees", tree)
    return bool(row is not None and json.loads(row["config"]).get("lookups"))


class SharedCorpus(DomainError):
    """An unscoped tree would ingest sources another tree already maps."""

    code = "shared-corpus"


def ingest_sources(conn: sqlite3.Connection, tree: str) -> tuple[str, ...]:
    """The sources an ingesting op (update/maintain) may mutate for ``tree``.

    ``scoped_sources`` with one refusal on top: an UNSCOPED tree maps every
    source, and once any other tree is registered that overlap is a
    corruption — both trees reconciling one set of section rows. A scoped tree
    cannot overlap (``_validate`` refuses the claim), so the only door left is
    the unscoped default, and this closes it at the moment it would do harm
    rather than at registration, which an existing database never re-runs.
    """
    if sources_of(conn, tree) is None:
        others = sorted(
            str(row["name"])
            for row in store.list_all(conn, "trees")
            if str(row["name"]) != tree
        )
        if others:
            raise SharedCorpus(
                f"tree {tree} is unscoped and would ingest sources that "
                f"belong to {', '.join(others)}; register it with its own "
                f"sources first (hrono tree config set {tree})"
            )
    return scoped_sources(conn, tree)


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
