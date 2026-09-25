"""Run an embedding model in-process, in batches, without crashing the worker.

``embed_texts`` batches an encoder call and guards allocation failures: on an
out-of-memory error it halves the batch and retries, degrading to size 1 before
failing cleanly, so a big input never takes down the worker. ``encoder_for``
builds the default ``sentence-transformers`` encoder for an in-process model
with a bounded load (a hung or missing backend fails with a clear reason, never
a traceback). The encoder is an injectable seam so tests run offline with a fake
emitting fixed-dim vectors.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Sequence

from hrono.errors import DomainError

Encoder = Callable[[list[str]], Sequence[Sequence[float]]]

_DEFAULT_BATCH = 32
_LOAD_TIMEOUT = 300.0


class EmbedError(DomainError):
    code = "embed-error"

    """Embedding could not run (reason is client-safe, never a traceback)."""


def embed_texts(
    texts: list[str], batch_size: int, encode: Encoder
) -> list[list[float]]:
    """Encode ``texts`` to vectors, halving the batch on an OOM failure."""
    vectors: list[list[float]] = []
    index = 0
    size = max(1, batch_size)
    while index < len(texts):
        batch = texts[index : index + size]
        try:
            encoded = encode(batch)
        except Exception as exc:  # noqa: BLE001 - degrade on allocation failure
            if not _is_oom(exc):
                raise
            if size == 1:
                raise EmbedError(
                    "out of memory embedding a single item"
                ) from exc
            size = max(1, size // 2)
            continue
        vectors.extend([list(vector) for vector in encoded])
        index += len(batch)
    return vectors


def batch_size(params: dict[str, object]) -> int:
    """Read the model's batch size, defaulting when unset."""
    value = params.get("batch_size")
    return int(value) if value is not None else _DEFAULT_BATCH


def encoder_for(
    model_id: str, *, load_timeout: float = _LOAD_TIMEOUT
) -> Encoder:
    """Build the in-process sentence-transformers encoder for ``model_id``."""
    model = _load(model_id, load_timeout)

    def encode(texts: list[str]) -> Sequence[Sequence[float]]:
        return [list(vector) for vector in model.encode(texts)]

    return encode


_CACHE: dict[str, Encoder] = {}
_CACHE_LOCK = threading.Lock()


def cached_encoder_for(
    model_id: str,
    *,
    load_timeout: float = _LOAD_TIMEOUT,
    build: Callable[[str], Encoder] | None = None,
) -> Encoder:
    """``encoder_for``, with the loaded model kept for the process's life.

    The weights are identical for every question and cost SECONDS to read from
    disk, so a caller that encodes once per request pays that over and over:
    `hrono recall` measured 11.9s then 7.7s against a 10s client timeout, and
    the CLI reported the product's read door as an unreachable server (#168).

    A long-lived process wants this; a one-shot op does not care either way. The
    lock is held across the load so a second caller arriving mid-load WAITS for
    the first model rather than reading a second copy of the weights into
    memory beside it.

    A FAILED load is not cached: the key is the model id, and an id that could
    not load once may load on the next attempt once whatever was wrong is
    fixed. Caching the failure would make the server need a restart to notice.
    """
    make = (
        build
        if build is not None
        else lambda name: encoder_for(name, load_timeout=load_timeout)
    )
    with _CACHE_LOCK:
        encoder = _CACHE.get(model_id)
        if encoder is None:
            encoder = make(model_id)
            _CACHE[model_id] = encoder
        return encoder


def _load(model_id: str, timeout: float) -> object:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise EmbedError(
            "in-process embedding backend is not installed"
        ) from exc

    box: dict[str, object] = {}

    def load() -> None:
        try:
            box["model"] = SentenceTransformer(model_id)
        except Exception as exc:  # noqa: BLE001 - surfaced below as EmbedError
            box["error"] = exc

    thread = threading.Thread(target=load, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise EmbedError(f"embedding model load timed out: {model_id}")
    if "error" in box:
        raise EmbedError(
            f"embedding model failed to load: {model_id}"
        ) from box["error"]  # type: ignore[misc]
    return box["model"]


def _is_oom(exc: Exception) -> bool:
    if isinstance(exc, MemoryError):
        return True
    text = str(exc).lower()
    return isinstance(exc, RuntimeError) and (
        "out of memory" in text or "cannot allocate" in text
    )
