"""The ``embed`` job op: vectorise stored content, content-addressed and once.

Resolves the target embedding model (named by the job scope, or the sole
embedding-kind model in the registry), selects the content hashes that have no
vector for it yet (#032 ``contents``), embeds only those in batches via the
injectable runner, and stores each vector keyed by (hash, model). A re-run finds
nothing missing (idempotent); a different model embeds under its own key. Reads
only local content — no secret — so it needs no cipher. Registers into the op
registry so the worker dispatches ``embed``.
"""

from __future__ import annotations

import json

from hrono.embed import store
from hrono.embed.runner import EmbedError, Encoder, batch_size, embed_texts
from hrono.embed.runner import encoder_for as _default_encoder_for
from hrono.ingest.store import get_content
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.registry import store as registry_store


def embed(
    job: Job,
    context: JobContext,
    *,
    encoder_for: object | None = None,
) -> None:
    """Embed every stored content hash missing a vector for the model."""
    factory = encoder_for if encoder_for is not None else _default_encoder_for
    config = _resolve_model(context, job.scope)
    model_name = str(config["name"])
    with context.database.connect() as conn:
        hashes = store.missing(conn, model_name)
        bodies = [get_content(conn, digest) for digest in hashes]
    if not hashes:
        return

    texts = [(body or b"").decode("utf-8", "replace") for body in bodies]
    encode: Encoder = factory(str(config["model"]))  # type: ignore[operator]
    vectors = embed_texts(texts, batch_size(_params(config)), encode)

    dims = _declared_dims(config)
    with context.database.connect() as conn, conn:
        for digest, vector in zip(hashes, vectors, strict=True):
            if dims is not None and len(vector) != dims:
                raise EmbedError(
                    f"embedding dims mismatch: declared {dims}, "
                    f"got {len(vector)}"
                )
            store.upsert_vector(conn, digest, model_name, vector)


def _resolve_model(
    context: JobContext, scope: dict[str, object]
) -> dict[str, object]:
    name = scope.get("name") if scope.get("type") == "model" else None
    with context.database.connect() as conn:
        if name is not None:
            row = registry_store.get(conn, "models", str(name))
            rows = [row] if row is not None else []
        else:
            rows = list(registry_store.list_all(conn, "models"))
    configs = [json.loads(r["config"]) for r in rows if r is not None]
    embedding = [c for c in configs if c.get("kind") == "embedding"]
    if not embedding:
        raise EmbedError("no embedding model available to embed with")
    if name is None and len(embedding) > 1:
        raise EmbedError("multiple embedding models — name one in the scope")
    return embedding[0]


def _params(config: dict[str, object]) -> dict[str, object]:
    params = config.get("params")
    return params if isinstance(params, dict) else {}


def _declared_dims(config: dict[str, object]) -> int | None:
    dims = _params(config).get("dims")
    return int(dims) if dims is not None else None


OPS["embed"] = embed
