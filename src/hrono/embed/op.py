"""The ``embed`` job op: vectorise stored content, content-addressed and once.

Resolves the target embedding model (named by the job scope, or the sole
embedding-kind model in the registry), selects the content hashes that have no
vector for it yet (#032 ``contents``), embeds only those in batches through the
encoder that model asks for — in process, or over HTTP when it names a
connection (#151) — and stores each vector keyed by (hash, model). A re-run
finds nothing missing (idempotent); a different model embeds under its own
key. A local model reads only local content and needs no cipher; a remote one
needs it to read its connection's key. Registers into the op
registry so the worker dispatches ``embed``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from hrono.cluster.blend import path_body
from hrono.embed import store
from hrono.embed.encoders import encoder_for_model
from hrono.embed.model import resolve_embedding_model
from hrono.embed.runner import EmbedError, Encoder, batch_size, embed_texts
from hrono.embed.runner import encoder_for as _default_encoder_for
from hrono.ingest.identity import content_hash
from hrono.ingest.store import get_content
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.registry.collections.trees import DEFAULT_TREE, sources_of


def embed(
    job: Job,
    context: JobContext,
    *,
    encoder_for: object | None = None,
) -> Mapping[str, int]:
    """Embed every stored content hash missing a vector; report how many."""
    factory = encoder_for if encoder_for is not None else _default_encoder_for
    with context.database.connect() as conn:
        config = resolve_embedding_model(conn, job.scope)
    model_name = str(config["name"])
    with context.database.connect() as conn:
        allowed = _allowed(conn, job.tree or DEFAULT_TREE)
        hashes = tuple(
            digest
            for digest in store.missing(conn, model_name)
            if allowed is None or digest in allowed
        )
        bodies = [get_content(conn, digest) for digest in hashes]
    if not hashes:
        return {"embedded": 0}

    texts = [(body or b"").decode("utf-8", "replace") for body in bodies]
    encode: Encoder = encoder_for_model(context, config, factory)
    vectors = embed_texts(texts, batch_size(_params(config)), encode)

    dims = _declared_dims(config)
    with context.database.write() as conn:
        for digest, vector in zip(hashes, vectors, strict=True):
            if dims is not None and len(vector) != dims:
                raise EmbedError(
                    f"embedding dims mismatch: declared {dims}, "
                    f"got {len(vector)}"
                )
            store.upsert_vector(conn, digest, model_name, vector)
    return {"embedded": len(hashes)}


def _allowed(conn: object, tree: str) -> frozenset[str] | None:
    """The content hashes ``tree`` may pay to embed, or None for all of them.

    Embed runs as a stage of ONE tree's build or sync, and an unscoped
    ``missing`` made that run vectorise every other tree's pending bodies too
    (and every orphan content row nothing references). The set is everything
    the tree's pipeline reads vectors for:

    - its sources' section and passage bodies;
    - its own nodes' brief sections and passages (their source is the
      synthetic ``node-<id>``);
    - the PATH strings of all of the above, which blend (#039) embeds as
      content keyed by the hash of the path's bytes — computable only here,
      so they are hashed in Python over the distinct paths;
    - each brief's whole text, which ``cluster_briefs`` registers as one body.
    """
    scope = sources_of(conn, tree)  # type: ignore[arg-type]
    if scope is None:
        return None
    named = json.dumps(list(scope))
    hashes: set[str] = set()
    paths: set[str] = set()
    for table in ("sections", "passages"):
        for row in conn.execute(  # type: ignore[attr-defined]
            f"SELECT DISTINCT content_hash, path FROM {table} "  # noqa: S608
            "WHERE source IN (SELECT value FROM json_each(?)) "
            "OR (source_type = 'node' AND source IN "
            "(SELECT 'node-' || id FROM nodes WHERE tree = ?))",
            (named, tree),
        ).fetchall():
            hashes.add(str(row["content_hash"]))
            paths.add(str(row["path"]))
    for row in conn.execute(  # type: ignore[attr-defined]
        "SELECT b.text AS text FROM briefs b "
        "JOIN nodes n ON n.id = b.node_id WHERE n.tree = ?",
        (tree,),
    ).fetchall():
        hashes.add(content_hash(str(row["text"]).encode("utf-8")))
    hashes.update(content_hash(path_body(path)) for path in paths)
    return frozenset(hashes)


def _params(config: dict[str, object]) -> dict[str, object]:
    params = config.get("params")
    return params if isinstance(params, dict) else {}


def _declared_dims(config: dict[str, object]) -> int | None:
    dims = _params(config).get("dims")
    return int(dims) if dims is not None else None


OPS["embed"] = embed
