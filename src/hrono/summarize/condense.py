"""The ``condense`` job op: the map stage over a scope's sections.

Resolves the text model (the sole ``text``-kind model, or the one named in the
job scope) and the seeded ``condense``-role prompt, then reduces each stored
section that has no condensation for that model to its essential information via
one completion call, caching the result by the section's content hash. An
unchanged section is never re-condensed (a re-run makes zero LLM calls) — the
incremental lever brief rebuilds stand on.

Lock discipline mirrors ``embed`` and clustering: load the pending sections +
the cached hashes UNDER the database lock, release it, make each LLM call
OUTSIDE the lock, and re-acquire only to persist that one result — so a section
that fails its call fails the leaf cleanly while every section condensed before
it is kept, and an idempotent re-run fills only the gaps. A section the model
refuses twice is recorded as refused for this model and prompt, so a re-run
skips it until its body, the model or the prompt changes, instead of paying two
calls on every sync to be refused again. No token cap and no truncation: the
recipe (every check, branch and call, identifiers verbatim) lives in the
prompt, not this code.

Because the calls are keyed by CONTENT HASH they are independent of each other,
so they run in ``pool.mapped``'s bounded worker pool rather than one at a time:
421 sections at 4-30 s each, serially, is 70 minutes of a process that is idle
for all of it. The persist stays on this thread, one at a time. And each call
carries up to ``packed.PACK_ITEMS`` sections, because through ``claude-code``
the call's own overhead, not the section, is most of what a build pays for.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping

from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import Completion
from hrono.llm.providers import client_for
from hrono.registry.collections.trees import DEFAULT_TREE, sources_of
from hrono.summarize import packed, pool, spend, store
from hrono.summarize.packed import Made
from hrono.summarize.resolve import resolve_prompt, resolve_text_model
from hrono.summarize.shape import talks_back

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
        paths = store.paths(conn, [digest for digest, _ in sections])
    if not sections:
        return {"condensed": 0}

    completion = client_for(context, model, "condense", client=client)

    def render(section: Section) -> str:
        # the file it came from, as the research prompt was given it: a
        # model that knows it reads a test, a migration or a template says so
        body = section[1].decode("utf-8", "replace")
        path = paths.get(section[0])
        return template.replace(
            _CONTENT_PLACEHOLDER, f"File: {path}\n\n{body}" if path else body
        )

    def call(pack: tuple[Section, ...]) -> list[Made]:
        return packed.condense_pack(completion, model, render, pack, talks_back)

    def keep(pack: tuple[Section, ...], made: list[Made]) -> None:
        for section, (result, refused) in zip(pack, made, strict=True):
            with context.database.write() as conn:
                if refused:  # never cached, never re-paid
                    store.refuse(
                        conn,
                        section[0],
                        model_name,
                        request,
                        refused,
                        result.text,
                    )
                    continue
                store.replace(
                    conn,
                    section[0],
                    model_name,
                    result.text,
                    result.usage.input_tokens,
                    result.usage.output_tokens,
                )

    condensed = [
        made
        for results in pool.mapped(
            packed.packs(sections),
            call,
            keep,
            workers=pool.width(),
            proceed=pool.running(context.database, job.id),
            named=lambda pack: _named(context, pack),
        )
        for made in results
    ]
    # an op that calls a model says what it spent: condense is the most
    # expensive stage of a first build, and must not be the one nobody can
    # account for.
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


def _named(context: JobContext, pack: tuple[Section, ...]) -> str:
    """The sections of a failed call by the files they are in.

    A pack fails as one call, so every section it carried is named: the one
    that broke it is among them, and which one cannot be known.
    """
    with context.database.connect() as conn:
        paths = [_path(conn, digest) for digest, _ in pack]
    return ("section " if len(paths) == 1 else "sections ") + ", ".join(paths)


def _path(conn: sqlite3.Connection, digest: str) -> str:
    row = conn.execute(
        "SELECT path FROM sections WHERE content_hash = ? LIMIT 1",
        (digest,),
    ).fetchone()
    return row["path"] if row else digest[:12]


OPS["condense"] = condense
