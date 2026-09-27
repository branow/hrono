"""The ``brief-upper`` op: pure-abstraction briefs for upper nodes (T22.2).

Above the leaf level a node summarises its CHILD BRIEFS, not source sections —
there is no condense stage above level 1 (summarization-experiments: "summarize
the summaries works"). This op writes the brief for each node at an upper level
(scope ``level``, default 1 — the first node-of-nodes level) from its children's
briefs, using the compact seeded ``brief-upper``-role prompt. Provenance,
mechanical references, staleness skip (#064), and outside-the-lock discipline
match #059; only the input (child briefs) and the prompt differ.

Child briefs are injected at ``{content}`` — the token #066 requires a
``brief-upper`` template to contain and the seeded default uses. References are
the child node ids, appended in code from membership, never LLM-written.
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
    resolve_prompt,
    resolve_text_model,
    template_hash,
)
from hrono.summarize.shape import answer

_CONTENT_PLACEHOLDER = "{content}"
_DEFAULT_LEVEL = 1
_DEFAULT_TREE = "default"


def brief_upper(
    job: Job,
    context: JobContext,
    *,
    client: Completion | None = None,
) -> Mapping[str, object]:
    """Write a brief per stale-or-missing upper node from its child briefs."""
    tree = job.tree or _DEFAULT_TREE
    level = _level(job.scope)
    with context.database.connect() as conn:
        held = len(pins.pinned(conn, pins.BRIEF))
        model = resolve_text_model(conn, job.scope, "brief-upper")
        model_name = str(model["name"])
        prompt_name, template = resolve_prompt(conn, "brief-upper")
        prompt_hash = template_hash(template)
        pending = [
            (
                node_id,
                briefs.child_briefs(conn, node_id),
                briefs.child_ids(conn, node_id),
                briefs.member_signature(conn, node_id),
            )
            for node_id in briefs.stale_or_missing(
                conn, tree, level, prompt_hash, model_name
            )
        ]
    pending = [(n, c, ids, s) for (n, c, ids, s) in pending if c]
    if not pending:
        return {"briefed": 0, "skipped_pinned": held}

    completion = client if client is not None else client_for(context, model)
    spent: list[tuple[int, int]] = []
    for node_id, child_texts, ids, signature in pending:
        source = "\n\n".join(child_texts)
        rendered = template.replace(_CONTENT_PLACEHOLDER, source)
        result, flagged = answer(
            completion,
            CompletionRequest(model=model, system="", content=rendered),
        )
        unfaithful = faithfulness(result.text, source)
        text = result.text
        with context.database.write() as conn:
            briefs.upsert(
                conn,
                node_id,
                text,
                model_name=model_name,
                prompt_name=prompt_name,
                prompt_hash=prompt_hash,
                member_signature=signature,
                unfaithful=json.dumps(unfaithful),
                flagged=flagged,
                members=json.dumps([f"node {node}" for node in ids]),
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
            )
            spent.append(
                (result.usage.input_tokens, result.usage.output_tokens)
            )
            store_brief(conn, node_id, text, signature)
    outcome: dict[str, object] = {
        "briefed": len(pending),
        "skipped_pinned": held,
    }
    tokens = spend.counts(spent)
    if tokens is not None:
        outcome["tokens"] = tokens
    return outcome


def _level(scope: dict[str, object]) -> int:
    level = scope.get("level")
    return int(level) if isinstance(level, int) else _DEFAULT_LEVEL


OPS["brief-upper"] = brief_upper
