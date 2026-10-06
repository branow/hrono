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
idempotent re-run fills only the gaps. A section the model refuses twice is
recorded as refused for this model and prompt (E015), so a re-run skips it
until its body, the model or the prompt changes, instead of paying two calls
on every sync to be refused again. No token cap and no truncation: the
recipe (identifiers verbatim, GOTCHA lines) lives in the prompt, not this code.

Because the calls are keyed by CONTENT HASH they are independent of each other,
so they run in ``pool.mapped``'s bounded worker pool rather than one at a time:
421 sections at 4-30 s each was 70 minutes of a process that was idle for all
of it. The persist stays on this thread, one at a time.
"""

from __future__ import annotations

from collections.abc import Mapping

from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import (
    Completion,
    CompletionRequest,
    CompletionResult,
)
from hrono.llm.providers import client_for
from hrono.registry.collections.trees import DEFAULT_TREE, sources_of
from hrono.summarize import pool, spend, store
from hrono.summarize.resolve import resolve_prompt, resolve_text_model
from hrono.summarize.shape import answer, talks_back

_CONTENT_PLACEHOLDER = "{content}"

Section = tuple[str, bytes]  # (content hash, section body)


def condense(
    job: Job,
    context: JobContext,
    *,
    client: Completion | None = None,
) -> Mapping[str, object]:
    """Condense every stored section missing a condensation for the model."""
    with context.database.connect() as conn:
        model = resolve_text_model(conn, job.scope, "condense")
        model_name = str(model["name"])
        _, template = resolve_prompt(conn, "condense")
        request = store.request_for(model, template)
        scope = sources_of(conn, job.tree or DEFAULT_TREE)
        sections = store.pending(
            conn, model_name, request=request, sources=scope
        )
    if not sections:
        return {"condensed": 0}

    completion = client_for(context, model, "condense", client=client)

    def call(section: Section) -> tuple[CompletionResult, str]:
        rendered = template.replace(
            _CONTENT_PLACEHOLDER, section[1].decode("utf-8", "replace")
        )
        return answer(
            completion,
            CompletionRequest(model=model, system="", content=rendered),
            talks_back,
        )

    def keep(section: Section, made: tuple[CompletionResult, str]) -> None:
        result, refused = made
        with context.database.write() as conn:
            if refused:  # never cached (#221), but never re-paid either (E015)
                store.refuse(
                    conn, section[0], model_name, request, refused, result.text
                )
                return
            store.replace(
                conn,
                section[0],
                model_name,
                result.text,
                result.usage.input_tokens,
                result.usage.output_tokens,
            )

    condensed = pool.mapped(
        sections,
        call,
        keep,
        workers=pool.width(),
        proceed=pool.running(context.database, job.id),
        named=lambda section: _named(context, section[0]),
    )
    # an op that calls a model says what it spent (#179); until now condense
    # reported nothing at all, which made the most expensive stage of a first
    # build the one nobody could account for.
    refused = sum(1 for _, flag in condensed if flag)
    outcome: dict[str, object] = {"condensed": len(condensed) - refused}
    if refused:
        outcome["refused"] = refused
    tokens = spend.counts(
        [(r.usage.input_tokens, r.usage.output_tokens) for r, _ in condensed]
    )
    if tokens is not None:
        outcome["tokens"] = tokens
    return outcome


def _named(context: JobContext, digest: str) -> str:
    """A section by the file it is in, for a failure's message (#213)."""
    with context.database.connect() as conn:
        row = conn.execute(
            "SELECT path FROM sections WHERE content_hash = ? LIMIT 1",
            (digest,),
        ).fetchone()
    return f"section {row['path'] if row else digest[:12]}"


OPS["condense"] = condense
