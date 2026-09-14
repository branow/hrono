"""The ``condense`` job op: the T20 map stage over a scope's sections.

Resolves the text model (the sole ``text``-kind model, or the one named in the
job scope) and the seeded ``condense``-role prompt, then reduces each stored
section that has no condensation for that model to its essential information via
one #057 completion call, caching the result by the section's content hash. An
unchanged section is never re-condensed (a re-run makes zero LLM calls) — the
incremental lever brief rebuilds stand on.

Lock discipline mirrors #035/#040: load the pending sections + the cached
hashes UNDER the #008 lock, release it, make each LLM call OUTSIDE the lock, and
re-acquire only to persist that one result — so a section that fails its call
fails the leaf cleanly while every section condensed before it is kept, and an
idempotent re-run fills only the gaps. No token cap and no truncation: the
recipe (identifiers verbatim, GOTCHA lines) lives in the prompt, not this code.
"""

from __future__ import annotations

from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import (
    AnthropicClient,
    Completion,
    CompletionRequest,
    LLMError,
)
from hrono.summarize import store
from hrono.summarize.resolve import resolve_prompt, resolve_text_model

_CONTENT_PLACEHOLDER = "{content}"


def condense(
    job: Job,
    context: JobContext,
    *,
    client: Completion | None = None,
) -> None:
    """Condense every stored section missing a condensation for the model."""
    with context.database.connect() as conn:
        model = resolve_text_model(conn, job.scope)
        model_name = str(model["name"])
        _, template = resolve_prompt(conn, "condense")
        sections = store.pending(conn, model_name)
    if not sections:
        return

    completion = client if client is not None else _default_client(context)
    for content_hash, body in sections:
        rendered = template.replace(
            _CONTENT_PLACEHOLDER, body.decode("utf-8", "replace")
        )
        result = completion.complete(
            CompletionRequest(model=model, system="", content=rendered)
        )
        with context.database.write() as conn:
            store.upsert(
                conn,
                content_hash,
                model_name,
                result.text,
                result.usage.input_tokens,
                result.usage.output_tokens,
            )


def _default_client(context: JobContext) -> Completion:
    if context.cipher is None:
        raise LLMError("no cipher available for the completion client")
    return AnthropicClient(context.database, context.cipher)


OPS["condense"] = condense
