"""The ``brief`` job op: the T21 reduce stage over bottom-level nodes.

Turns each bottom-level topic (#040 node) into a stored brief by rendering the
seeded ``brief``-role prompt over its member sections' condensations (#058) via
one #057 completion call, then appending the member reference URIs MECHANICALLY
from node membership — the LLM never writes a reference. Each brief records
provenance (model, prompt name + template hash, token usage) that #064 freshness
and the cost API read back.

A node that already has a brief is skipped, so a re-run over unchanged nodes
makes zero LLM calls (membership-change invalidation is #064, out of scope).
Lock discipline mirrors #058/#035: gather the nodes and their condensations
UNDER the #008 lock, release it, make each LLM call OUTSIDE the lock, re-acquire
only to persist that node — so a failing node fails its leaf cleanly and an
idempotent re-run fills only the gaps.
"""

from __future__ import annotations

import hashlib
import json

from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import (
    AnthropicClient,
    Completion,
    CompletionRequest,
    LLMError,
)
from hrono.recall.brief_passages import store_brief
from hrono.summarize import briefs
from hrono.summarize.faithfulness import faithfulness
from hrono.summarize.resolve import resolve_prompt, resolve_text_model

_CONTENT_PLACEHOLDER = "{content}"
_LEVEL = 0
_DEFAULT_TREE = "default"


def brief(
    job: Job,
    context: JobContext,
    *,
    client: Completion | None = None,
) -> None:
    """Write a brief per stale-or-missing bottom-level node, with provenance."""
    tree = job.tree or _DEFAULT_TREE
    with context.database.connect() as conn:
        model = resolve_text_model(conn, job.scope)
        model_name = str(model["name"])
        prompt_name, template = resolve_prompt(conn, "brief")
        prompt_hash = _hash(template)
        pending = [
            (
                node_id,
                briefs.member_condensations(conn, node_id, model_name),
                briefs.member_uris(conn, node_id),
                briefs.member_signature(conn, node_id),
            )
            for node_id in briefs.stale_or_missing(
                conn, tree, _LEVEL, prompt_hash, model_name
            )
        ]
    pending = [(n, c, u, s) for (n, c, u, s) in pending if c]
    if not pending:
        return

    completion = client if client is not None else _default_client(context)
    for node_id, condensations, uris, signature in pending:
        source = "\n\n".join(condensations)
        rendered = template.replace(_CONTENT_PLACEHOLDER, source)
        result = completion.complete(
            CompletionRequest(model=model, system="", content=rendered)
        )
        unfaithful = faithfulness(result.text, source)
        text = result.text + _references(uris)
        with context.database.connect() as conn, conn:
            briefs.upsert(
                conn,
                node_id,
                text,
                model_name=model_name,
                prompt_name=prompt_name,
                prompt_hash=prompt_hash,
                member_signature=signature,
                unfaithful=json.dumps(unfaithful),
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
            )
            store_brief(conn, node_id, text, signature)


def _references(uris: tuple[str, ...]) -> str:
    if not uris:
        return ""
    return "\n\nReferences:\n" + "\n".join(f"- {uri}" for uri in uris)


def _hash(template: str) -> str:
    return hashlib.sha256(template.encode("utf-8")).hexdigest()


def _default_client(context: JobContext) -> Completion:
    if context.cipher is None:
        raise LLMError("no cipher available for the completion client")
    return AnthropicClient(context.database, context.cipher)


OPS["brief"] = brief
