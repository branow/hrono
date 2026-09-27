"""The ``brief`` job op: the T21 reduce stage over bottom-level nodes.

Turns each bottom-level topic (#040 node) into a stored brief by rendering the
seeded ``brief``-role prompt over its member sections' condensations (#058) via
one #057 completion call, then appending the member reference URIs MECHANICALLY
from node membership — the LLM never writes a reference. Each brief records
provenance (model, prompt name + template hash, token usage) that #064 freshness
and the cost API read back.

The member URIs are stored BESIDE the text, not inside it (#102): #071 splits a
brief into node:// passages, and a path list is lexically dense enough to
outrank real prose for a keyword-ish question — one QA query got five slices of
a URI list as its best "summary" hits. The export renderer re-attaches them, so
the map still shows every reference; only the indexed passages change.

A reply that is not a summary at all — a question back to the caller, an
assistant refusal — is retried ONCE and then stored WITH a flag (#103): the
faithfulness gate cannot catch it, because a non-answer invents nothing, and
dropping the node would cost the map a whole topic.

A node that already has a brief is skipped, so a re-run over unchanged nodes
makes zero LLM calls (membership-change invalidation is #064, out of scope).
Lock discipline mirrors #058/#035: gather the nodes and their condensations
UNDER the #008 lock, release it, make each LLM call OUTSIDE the lock, re-acquire
only to persist that node — so a failing node fails its leaf cleanly and an
idempotent re-run fills only the gaps.
"""

from __future__ import annotations

import json
from collections.abc import Mapping

from hrono import pins
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import (
    Completion,
    CompletionRequest,
)
from hrono.llm.providers import client_for
from hrono.recall.brief_passages import store_brief
from hrono.summarize import briefs, spend
from hrono.summarize.faithfulness import faithfulness
from hrono.summarize.resolve import (
    model_fingerprint,
    producer_model_name,
    resolve_prompt,
    resolve_text_model,
    template_hash,
)
from hrono.summarize.shape import answer

_CONTENT_PLACEHOLDER = "{content}"
_LEVEL = 0
_DEFAULT_TREE = "default"


def brief(
    job: Job,
    context: JobContext,
    *,
    client: Completion | None = None,
) -> Mapping[str, object]:
    """Write a brief per stale-or-missing bottom-level node, with provenance."""
    tree = job.tree or _DEFAULT_TREE
    with context.database.connect() as conn:
        held = len(pins.pinned(conn, pins.BRIEF))
        model = resolve_text_model(conn, job.scope, "brief")
        model_name = str(model["name"])
        # the condensations were written by the CONDENSE model (#067): reading
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
                conn, tree, _LEVEL, prompt_hash, model_name, fingerprint
            )
        ]
    pending = [(n, i, s) for (n, i, s) in pending if i.texts]
    if not pending:
        return {"briefed": 0, "skipped_pinned": held}

    completion = client if client is not None else client_for(context, model)
    spent: list[tuple[int, int]] = []
    for node_id, inputs, signature in pending:
        source = "\n\n".join(inputs.texts)
        rendered = template.replace(_CONTENT_PLACEHOLDER, source)
        result, flagged = answer(
            completion,
            CompletionRequest(model=model, system="", content=rendered),
        )
        unfaithful = faithfulness(result.text, source)
        text = result.text
        flagged = flagged or _uncondensed(inputs.dropped)
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
                unfaithful=json.dumps(unfaithful),
                flagged=flagged,
                members=json.dumps(list(inputs.uris)),
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
            )
            store_brief(conn, node_id, text, signature)
        spent.append((result.usage.input_tokens, result.usage.output_tokens))
    # what a pin HELD is as much the run's outcome as what it wrote: an
    # operator who sees "briefed 0" needs to know whether there was nothing to
    # do or whether they froze it themselves (#154).
    outcome: dict[str, object] = {
        "briefed": len(pending),
        "skipped_pinned": held,
    }
    tokens = spend.counts(spent)
    if tokens is not None:
        outcome["tokens"] = tokens
    return outcome


def _uncondensed(dropped: int) -> str:
    """#122: a member that contributed nothing is a flag, never a silence."""
    if dropped == 0:
        return ""
    return f"{dropped} member section(s) had no condensation to reduce"


OPS["brief"] = brief
