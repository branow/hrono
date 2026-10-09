"""Which encoder an embedding model resolves to.

A model with NO connection loads in process; a model WITH one is reached over
HTTP, and its provider says how.
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
from hrono.llm.ledger import Tally, metered
from hrono.llm.providers import provider_for

LOCAL = "local"  # the ledger's provider for a model loaded in process

Builder = Callable[[JobContext, dict[str, object], Tally], Encoder]


def _openai(
    context: JobContext, model: dict[str, object], tally: Tally
) -> Encoder:
    return openai.embeddings(  # type: ignore[return-value]
        context.database, context.cipher, model, tally=tally
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
    """Build the encoder this model asks for: in process, or over HTTP.

    Either way each batch it embeds is recorded in the usage ledger.
    """
    if config.get("connection") is None:
        encode = local(str(config["model"]))  # type: ignore[operator]
        return metered(encode, context, config, provider=LOCAL)
    provider = provider_for(context, config)
    builder = ENCODERS.get(provider)
    if builder is None:
        raise EmbedError(
            f"provider cannot serve an embedding model: {provider}"
        )
    tally = Tally()
    return metered(
        builder(context, config, tally),
        context,
        config,
        provider=provider,
        tally=tally,
    )
