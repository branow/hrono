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
import sqlite3
from collections.abc import Mapping
from typing import NamedTuple

from hrono import pins
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import (
    Completion,
    CompletionRequest,
    CompletionResult,
    summed,
)
from hrono.llm.providers import client_for
from hrono.recall.brief_passages import store_brief
from hrono.registry.collections.trees import DEFAULT_TREE, looks_up
from hrono.summarize import briefs, lookup, pool, spend
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
    text: str  # the brief, without the lookups' Used and Lookups sections
    uses: tuple[lookup.Use, ...] = ()
    lookups: str = ""  # JSON: the tool calls and the writer's own account


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
        # a tree that looks things up asks more of the same prompt, so its
        # briefs are written - and kept fresh - against the longer one
        looking = looks_up(conn, tree)
        asked = template + (lookup.INSTRUCTION if looking else "")
        prompt_hash = template_hash(asked)
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
    found = lookup.Files({})
    own: dict[int, set[str]] = {}
    if looking:
        with context.database.connect() as conn:
            found = lookup.files(conn, tree, source_model)
            own = {node: _own_files(conn, node) for node, _, _ in pending}

    completion = client_for(context, model, "brief", client=client)

    def call(entry: Pending) -> Written:
        node_id, inputs, _ = entry
        source = inputs.rendered
        if not looking:
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
                result.text,
            )
        rendered = asked.replace(
            _CONTENT_PLACEHOLDER, _with_paths(inputs, own[node_id])
        )
        tools = lookup.toolbox(found, own[node_id])
        result, flagged = answer(
            completion,
            CompletionRequest(
                model=model, system="", content=rendered, tools=tools
            ),
            brief_gate(template, source),
        )
        calls = list(tools.calls)
        missing = lookup.unsearched(result.text)
        if not calls or missing:
            # half the bcreg v10 leaf briefs looked nothing up, and most of
            # the rest named connections they never searched: each is asked
            # again, once, with a fresh budget, to look first
            first = result
            retry = lookup.toolbox(found, own[node_id])
            result, flagged = answer(
                completion,
                CompletionRequest(
                    model=model,
                    system="",
                    content=rendered + lookup.again(missing, bool(calls)),
                    tools=retry,
                ),
                brief_gate(template, source),
            )
            result = summed([first, result])
            calls += retry.calls
        text, uses = lookup.split(result.text, own[node_id], found.texts)
        # what it looked up is material too: a name it read in another
        # topic's file is not an invention
        read = "\n\n".join(
            found.texts.get(lookup.CONDENSED + u.file + ".md", "")
            + "\n"
            + found.texts.get(lookup.SOURCE + u.file, "")
            for u in uses
        )
        return Written(
            result,
            flagged or _uncondensed(inputs.dropped),
            json.dumps(faithfulness(text, source + "\n\n" + read)),
            text,
            uses,
            json.dumps(
                {
                    "calls": calls,
                    "account": lookup.accounting(result.text),
                }
            ),
        )

    def keep(entry: Pending, written: Written) -> None:
        node_id, inputs, signature = entry
        text = written.text
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
            lookup.store_uses(conn, node_id, written.uses)
            conn.execute(
                "UPDATE briefs SET lookups = ? WHERE node_id = ?",
                (written.lookups, node_id),
            )

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


def _own_files(conn: sqlite3.Connection, node_id: int) -> set[str]:
    """A topic's member files, as ``<source>/<path>``."""
    return {
        f"{row['source']}/{row['path']}"
        for row in conn.execute(
            "SELECT s.source AS source, s.path AS path FROM node_members m "
            "JOIN sections s ON s.id = m.section_id WHERE m.node_id = ?",
            (node_id,),
        )
    }


def _with_paths(inputs: briefs.ReduceInput, own: set[str]) -> str:
    """The topic's condensations, each under the path the tools use.

    Measured: labelled by path alone, the writer guessed the tools' paths
    without their source, found nothing and stopped looking.
    """
    full = {name.partition("/")[2]: name for name in own}
    return briefs.labeled(
        (lookup.SOURCE + full.get(label, label), text)
        for label, text in zip(inputs.labels, inputs.texts, strict=True)
    )


def _uncondensed(dropped: int) -> str:
    """A member that contributed nothing is a flag, never a silence."""
    if dropped == 0:
        return ""
    return f"{dropped} member section(s) had no condensation to reduce"


OPS["brief"] = brief
