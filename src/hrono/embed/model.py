"""Resolve which embedding model a job works under.

Both the ``embed`` op (which writes vectors) and the ``cluster`` op (which reads
them back to blend and group) must agree on the model whose vectors to use, so
the selection rule lives here once: the embedding-kind model named in the job
scope, or the sole embedding-kind model in the registry when none is named.
"""

from __future__ import annotations

import json
import sqlite3

from hrono.embed.runner import EmbedError
from hrono.registry import store as registry_store


def resolve_embedding_model(
    conn: sqlite3.Connection, scope: dict[str, object]
) -> dict[str, object]:
    """Return the embedding model config for ``scope``, or raise EmbedError."""
    name = scope.get("name") if scope.get("type") == "model" else None
    if name is not None:
        row = registry_store.get(conn, "models", str(name))
        rows = [row] if row is not None else []
    else:
        rows = list(registry_store.list_all(conn, "models"))
    configs = [json.loads(r["config"]) for r in rows if r is not None]
    embedding = [c for c in configs if c.get("kind") == "embedding"]
    if not embedding:
        raise EmbedError("no embedding model available")
    if name is None and len(embedding) > 1:
        raise EmbedError("multiple embedding models — name one in the scope")
    return embedding[0]
