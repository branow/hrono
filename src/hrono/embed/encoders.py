"""Which encoder an embedding model resolves to (#151, T44.1).

A model with NO connection loads in process, which is what every model did
before this; a model WITH one is reached over HTTP, and its provider says how.
The decision is the same one the completion side makes (`providers.client_for`)
and reads the same field, so a connection means the same thing to both halves
of the system.

The local factory stays an injectable seam: ops pass a fake encoder in tests,
and that must keep working for local models without pretending a remote one is
local.
"""

from __future__ import annotations

from collections.abc import Callable

from hrono.embed.runner import EmbedError, Encoder
from hrono.jobs.ops import JobContext
from hrono.llm import openai
from hrono.llm.providers import provider_for

Builder = Callable[[JobContext, dict[str, object]], Encoder]


def _openai(context: JobContext, model: dict[str, object]) -> Encoder:
    return openai.embeddings(  # type: ignore[return-value]
        context.database, context.cipher, model
    )


ENCODERS: dict[str, Builder] = {
    "openai": _openai,
    "openai-compatible": _openai,
}


def encoder_for_model(
    context: JobContext,
    config: dict[str, object],
    local: object,
) -> Encoder:
    """Build the encoder this model asks for: in process, or over HTTP."""
    if config.get("connection") is None:
        return local(str(config["model"]))  # type: ignore[operator, no-any-return]
    provider = provider_for(context, config)
    builder = ENCODERS.get(provider)
    if builder is None:
        raise EmbedError(
            f"provider cannot serve an embedding model: {provider}"
        )
    return builder(context, config)
