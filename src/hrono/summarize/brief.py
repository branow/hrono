"""The ``brief`` job op: the reduce stage over bottom-level nodes.

Turns each bottom-level topic (a level-0 node) into a stored brief by rendering
the seeded ``brief``-role prompt over its member sections' condensations via one
completion call, then appending the member reference URIs MECHANICALLY from node
membership — the LLM never writes a reference. Each brief records provenance
(model, prompt name + template hash, token usage) that brief freshness and the
cost API read back.

The member URIs are stored BESIDE the text, not inside it: recall splits a brief
into node:// passages, and a path list is lexically dense enough to outrank real
prose for a keyword-ish question — one test query got five slices of a URI list
as its best "summary" hits. The export renderer re-attaches them, so the map
still shows every reference; only the indexed passages change.

A reply that is not a summary at all — a question back to the caller, an
assistant refusal — is retried ONCE and then stored WITH a flag: the
faithfulness gate cannot catch it, because a non-answer invents nothing, and
dropping the node would cost the map a whole topic.

A node whose brief is FRESH is skipped — ``stale_or_missing`` compares the
member signature, prompt hash and model fingerprint — so a re-run over
unchanged nodes makes zero LLM calls.
Lock discipline mirrors ``condense`` and ``embed``: gather the nodes and their
condensations UNDER the database lock, release it, make each LLM call OUTSIDE
the lock, re-acquire only to persist that node — so a failing node fails its
leaf cleanly and an idempotent re-run fills only the gaps. One node's call tells
another's nothing, so they run in ``pool.mapped``'s bounded pool; only the
persist is serial.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import NamedTuple

from hrono import pins
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import (
    Completion,
    CompletionRequest,
    CompletionResult,
)
from hrono.llm.providers import client_for
from hrono.recall.brief_passages import store_brief
from hrono.registry.collections.trees import DEFAULT_TREE
from hrono.summarize import briefs, pool, spend
from hrono.summarize.faithfulness import faithfulness
from hrono.summarize.resolve import (
    model_fingerprint,
    producer_model_name,
    resolve_prompt,
    resolve_text_model,
    template_hash,
)
from hrono.summarize.shape import answer, brief_gate

_CONTENT_PLACEHOLDER = "{content}"
_LEVEL = 0
Pending = tuple[int, briefs.ReduceInput, str]  # node, inputs, signature


class Written(NamedTuple):
    """One node's completed brief, computed off the lock and not yet stored."""

    result: CompletionResult
    flagged: str
    unfaithful: str


def brief(
    job: Job,
    context: JobContext,
    *,
    client: Completion | None = None,
) -> Mapping[str, object]:
    """Write a brief per stale-or-missing bottom-level node, with provenance."""
    tree = job.tree or DEFAULT_TREE
    with context.database.connect() as conn:
        held = len(pins.pinned(conn, pins.BRIEF))
        model = resolve_text_model(conn, job.scope, "brief")
        model_name = str(model["name"])
        # the condensations were written by the CONDENSE model: reading
        # them under this op's own name finds none the moment the two differ,
        # and briefs nothing without saying so.
        source_model = producer_model_name(conn, job.scope, "condense")
        prompt_name, template = resolve_prompt(conn, "brief")
        prompt_hash = template_hash(template)
        fingerprint = model_fingerprint(model)
        pending = [
            (
                node_id,
                briefs.reduce_input(conn, node_id, source_model),
                briefs.member_signature(conn, node_id),
            )
            for node_id in briefs.stale_or_missing(
                conn,
                tree,
                _LEVEL,
                prompt_hash,
                model_name,
                fingerprint,
                only=briefs.scoped_node(job.scope),
            )
        ]
    pending = [(n, i, s) for (n, i, s) in pending if i.texts]
    if not pending:
        return {"briefed": 0, "skipped_pinned": held}

    completion = client_for(context, model, "brief", client=client)

    def call(entry: Pending) -> Written:
        _, inputs, _ = entry
        source = "\n\n".join(inputs.texts)
        rendered = template.replace(_CONTENT_PLACEHOLDER, source)
        result, flagged = answer(
            completion,
            CompletionRequest(model=model, system="", content=rendered),
            brief_gate(template, source),
        )
        return Written(
            result,
            flagged or _uncondensed(inputs.dropped),
            json.dumps(faithfulness(result.text, source)),
        )

    def keep(entry: Pending, written: Written) -> None:
        node_id, inputs, signature = entry
        text = written.result.text
        with context.database.write() as conn:
            briefs.upsert(
                conn,
                node_id,
                text,
                model_name=model_name,
                prompt_name=prompt_name,
                prompt_hash=prompt_hash,
                model_fingerprint=fingerprint,
                member_signature=signature,
                unfaithful=written.unfaithful,
                flagged=written.flagged,
                members=json.dumps(list(inputs.uris)),
                source_model=source_model,
                input_tokens=written.result.usage.input_tokens,
                output_tokens=written.result.usage.output_tokens,
            )
            store_brief(conn, node_id, text, signature)

    briefed = pool.mapped(
        pending,
        call,
        keep,
        workers=pool.width(),
        proceed=pool.running(context.database, job.id),
        named=lambda entry: f"topic {entry[0]}",
    )
    # what a pin HELD is as much the run's outcome as what it wrote: an
    # operator who sees "briefed 0" needs to know whether there was nothing to
    # do or whether they froze it themselves.
    outcome: dict[str, object] = {
        "briefed": len(briefed),
        "skipped_pinned": held,
    }
    tokens = spend.counts(
        [
            (w.result.usage.input_tokens, w.result.usage.output_tokens)
            for w in briefed
        ]
    )
    if tokens is not None:
        outcome["tokens"] = tokens
    return outcome


def _uncondensed(dropped: int) -> str:
    """A member that contributed nothing is a flag, never a silence."""
    if dropped == 0:
        return ""
    return f"{dropped} member section(s) had no condensation to reduce"


OPS["brief"] = brief
