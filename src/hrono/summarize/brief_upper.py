"""The ``brief-upper`` op: pure-abstraction briefs for upper nodes.

Above the leaf level a node summarises its CHILD BRIEFS, not source sections —
there is no condense stage above level 1 (docs/summarization.md: "summarize the
summaries works"). This op writes the brief for each node at an upper level
(scope ``level``, default 1 — the first node-of-nodes level) from its children's
briefs, using the compact seeded ``brief-upper``-role prompt. Provenance,
mechanical references, staleness skip, and outside-the-lock discipline match
``brief`` — including the bounded ``pool.mapped`` the calls run in, with the
persist serial on this thread; only the input (child briefs) and the prompt
differ.

Child briefs are injected at ``{content}`` — the token prompt validation
requires a ``brief-upper`` template to contain and the seeded default uses.
References are the child node ids, appended in code from membership, never
LLM-written.
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
    resolve_prompt,
    resolve_text_model,
    template_hash,
)
from hrono.summarize.shape import answer, brief_gate

_CONTENT_PLACEHOLDER = "{content}"
_DEFAULT_LEVEL = 1
# node, its children's briefs, those children's ids, member signature
Pending = tuple[int, tuple[str, ...], tuple[int, ...], str]


class Written(NamedTuple):
    """One upper node's brief, computed off the lock and not yet stored."""

    result: CompletionResult
    flagged: str
    unfaithful: str


def brief_upper(
    job: Job,
    context: JobContext,
    *,
    client: Completion | None = None,
) -> Mapping[str, object]:
    """Write a brief per stale-or-missing upper node from its child briefs."""
    tree = job.tree or DEFAULT_TREE
    level = _level(job.scope)
    with context.database.connect() as conn:
        held = len(pins.pinned(conn, pins.BRIEF))
        model = resolve_text_model(conn, job.scope, "brief-upper")
        model_name = str(model["name"])
        prompt_name, template = resolve_prompt(conn, "brief-upper")
        prompt_hash = template_hash(template)
        fingerprint = model_fingerprint(model)
        pending = [
            (
                node_id,
                briefs.child_briefs(conn, node_id),
                briefs.child_ids(conn, node_id),
                briefs.member_signature(conn, node_id),
            )
            for node_id in briefs.stale_or_missing(
                conn,
                tree,
                level,
                prompt_hash,
                model_name,
                fingerprint,
                only=briefs.scoped_node(job.scope),
            )
        ]
    pending = [(n, c, ids, s) for (n, c, ids, s) in pending if c]
    if not pending:
        return {"briefed": 0, "skipped_pinned": held}

    completion = client_for(context, model, "brief-upper", client=client)

    def call(entry: Pending) -> Written:
        source = "\n\n".join(entry[1])
        rendered = template.replace(_CONTENT_PLACEHOLDER, source)
        result, flagged = answer(
            completion,
            CompletionRequest(model=model, system="", content=rendered),
            brief_gate(template, source),
        )
        return Written(
            result, flagged, json.dumps(faithfulness(result.text, source))
        )

    def keep(entry: Pending, written: Written) -> None:
        node_id, _, ids, signature = entry
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
                members=json.dumps([f"node {node}" for node in ids]),
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


def _level(scope: dict[str, object]) -> int:
    level = scope.get("level")
    return int(level) if isinstance(level, int) else _DEFAULT_LEVEL


OPS["brief-upper"] = brief_upper
