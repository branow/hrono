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

import json
import sqlite3

from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import (
    AnthropicClient,
    Completion,
    CompletionRequest,
    LLMError,
)
from hrono.registry import store as registry_store
from hrono.summarize import store

_CONTENT_PLACEHOLDER = "{content}"


def condense(
    job: Job,
    context: JobContext,
    *,
    client: Completion | None = None,
) -> None:
    """Condense every stored section missing a condensation for the model."""
    with context.database.connect() as conn:
        model = _resolve_text_model(conn, job.scope)
        model_name = str(model["name"])
        template = _condense_template(conn)
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
        with context.database.connect() as conn, conn:
            store.upsert(
                conn,
                content_hash,
                model_name,
                result.text,
                result.usage.input_tokens,
                result.usage.output_tokens,
            )


def _resolve_text_model(
    conn: sqlite3.Connection, scope: dict[str, object]
) -> dict[str, object]:
    name = scope.get("name") if scope.get("type") == "model" else None
    if name is not None:
        row = registry_store.get(conn, "models", str(name))
        rows = [row] if row is not None else []
    else:
        rows = list(registry_store.list_all(conn, "models"))
    configs = [json.loads(r["config"]) for r in rows if r is not None]
    text = [c for c in configs if c.get("kind") == "text"]
    if not text:
        raise LLMError("no text model available")
    if name is None and len(text) > 1:
        raise LLMError("multiple text models — name one in the scope")
    return text[0]


def _condense_template(conn: sqlite3.Connection) -> str:
    configs = [
        json.loads(row["config"])
        for row in registry_store.list_all(conn, "prompts")
    ]
    matches = [c for c in configs if c.get("role") == "condense"]
    if not matches:
        raise LLMError("no condense prompt configured")
    if len(matches) > 1:
        raise LLMError("multiple condense prompts configured")
    return str(matches[0]["template"])


def _default_client(context: JobContext) -> Completion:
    if context.cipher is None:
        raise LLMError("no cipher available for the completion client")
    return AnthropicClient(context.database, context.cipher)


OPS["condense"] = condense
