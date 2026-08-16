"""Resolve a scope selector into items and fan a parent job into leaves.

Selectors are data-driven (one resolver per ``type``): ``all`` and ``source``
resolve now; ``section``/``node``/``level`` are seamed but not yet supported
(they need tree entities in M3). Fan-out creates a parent plus one atomic leaf
per resolved item, so the worker's failure-isolation applies per item.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from hrono.db.database import Database
from hrono.errors import BadRequest, NotFound
from hrono.jobs import store
from hrono.jobs.model import serialize_scope
from hrono.registry import store as registry_store

Resolver = Callable[[Database, dict[str, object]], list[dict[str, object]]]


def resolve(
    database: Database, scope: dict[str, object] | None
) -> list[dict[str, object]]:
    """Resolve a scope selector into a list of concrete single-item scopes."""
    selector = scope if scope else {"type": "all"}
    kind = str(selector.get("type", "all"))
    resolver = _RESOLVERS.get(kind)
    if resolver is None:
        raise BadRequest(f"unknown scope type: {kind}")
    return resolver(database, selector)


def fan_out(
    database: Database,
    op: str,
    scope: dict[str, object] | None,
    *,
    tree: str | None = None,
) -> str:
    """Create a parent + one leaf per resolved item; return the parent id."""
    items = resolve(database, scope)
    parent_id = _job_id()
    leaves = [(_job_id(), serialize_scope(item)) for item in items]
    parent_scope = serialize_scope(scope if scope else {"type": "all"})
    with database.connect() as conn:
        store.create_fanout(
            conn, parent_id, op, parent_scope, leaves, tree, _now()
        )
    return parent_id


def _resolve_all(
    database: Database, selector: dict[str, object]
) -> list[dict[str, object]]:
    with database.connect() as conn:
        rows = registry_store.list_all(conn, "sources")
    return [{"type": "source", "name": row["name"]} for row in rows]


def _resolve_source(
    database: Database, selector: dict[str, object]
) -> list[dict[str, object]]:
    name = str(selector["name"])
    with database.connect() as conn:
        row = registry_store.get(conn, "sources", name)
    if row is None:
        raise NotFound(f"unknown source: {name}")
    return [{"type": "source", "name": name}]


def _not_supported(
    database: Database, selector: dict[str, object]
) -> list[dict[str, object]]:
    raise BadRequest(f"scope type not yet supported: {selector['type']}")


_RESOLVERS: dict[str, Resolver] = {
    "all": _resolve_all,
    "source": _resolve_source,
    "section": _not_supported,
    "node": _not_supported,
    "level": _not_supported,
}


def _job_id() -> str:
    return f"job_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
