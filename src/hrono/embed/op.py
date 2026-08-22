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

from hrono.embed import store
from hrono.embed.model import resolve_embedding_model
from hrono.embed.runner import EmbedError, Encoder, batch_size, embed_texts
from hrono.embed.runner import encoder_for as _default_encoder_for
from hrono.ingest.store import get_content
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext


def embed(
    job: Job,
    context: JobContext,
    *,
    encoder_for: object | None = None,
) -> None:
    """Embed every stored content hash missing a vector for the model."""
    factory = encoder_for if encoder_for is not None else _default_encoder_for
    with context.database.connect() as conn:
        config = resolve_embedding_model(conn, job.scope)
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


def _params(config: dict[str, object]) -> dict[str, object]:
    params = config.get("params")
    return params if isinstance(params, dict) else {}


def _declared_dims(config: dict[str, object]) -> int | None:
    dims = _params(config).get("dims")
    return int(dims) if dims is not None else None


OPS["embed"] = embed
