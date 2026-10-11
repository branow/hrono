"""The ``brief-preview`` op: what an unsaved prompt would write for one topic.

Changing a brief prompt makes every brief it wrote stale, and the re-brief
that follows costs the whole tree. This op lets a curator see one topic's
brief under the edited template first, beside the brief it would
replace.

It is the real thing run on one topic and stored nowhere: the same model the
real stage resolves, the same inputs the real stage reduces (a topic's section
condensations, or its child briefs above the bottom level), the same
retry-once gate. The template is the scope's, not the registry's, so nothing
is saved to config; the reply goes into the job's `result` and not into
`briefs`, so nothing in the tree moves. The calls are ledgered against this
job like any other, so the spend shows on Usage.

The result carries prose, which a result otherwise never does (`jobs.model`):
the preview IS the reply, and it has no better place that is not the tree.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping

from hrono import edits
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import Completion, CompletionRequest, LLMError
from hrono.llm.providers import client_for
from hrono.registry.collections.trees import DEFAULT_TREE
from hrono.summarize import briefs, spend
from hrono.summarize.resolve import producer_model_name, resolve_text_model
from hrono.summarize.shape import answer, brief_gate

ROLES = ("brief", "brief-upper")
_CONTENT_PLACEHOLDER = "{content}"
_BOTTOM = 0


def brief_preview(
    job: Job,
    context: JobContext,
    *,
    client: Completion | None = None,
) -> Mapping[str, object]:
    """Write one topic's brief under ``scope["template"]``, and keep nothing."""
    tree = job.tree or DEFAULT_TREE
    node = briefs.scoped_node(job.scope)
    role = str(job.scope.get("role"))
    template = str(job.scope.get("template") or "")
    if node is None or role not in ROLES:
        raise LLMError("a preview needs a topic, a brief role and a template")
    if _CONTENT_PLACEHOLDER not in template:
        raise LLMError(f"the template must contain {_CONTENT_PLACEHOLDER}")
    with context.database.connect() as conn:
        if not edits.node_exists(conn, tree, node):
            raise LLMError(f"topic not found in tree {tree}: {node}")
        model = resolve_text_model(conn, job.scope, role)
        source = _source(conn, node, role, job)
    completion = client_for(context, model, role, client=client)
    result, flagged = answer(
        completion,
        CompletionRequest(
            model=model,
            system="",
            content=template.replace(_CONTENT_PLACEHOLDER, source),
        ),
        brief_gate(template, source),
    )
    outcome: dict[str, object] = {"text": result.text, "flagged": flagged}
    tokens = spend.counts(
        [(result.usage.input_tokens, result.usage.output_tokens)]
    )
    if tokens is not None:
        outcome["tokens"] = tokens
    return outcome


def _source(conn: sqlite3.Connection, node: int, role: str, job: Job) -> str:
    """What the real stage for this role would reduce for ``node``."""
    level = int(
        conn.execute(
            "SELECT level FROM nodes WHERE id = ?", (node,)
        ).fetchone()[0]
    )
    if (role == "brief") != (level == _BOTTOM):
        raise LLMError(
            f"a {role} prompt does not write for a level {level} topic"
        )
    if role == "brief":
        source = briefs.reduce_input(
            conn, node, producer_model_name(conn, job.scope, "condense")
        ).rendered
    else:
        source = briefs.labeled(briefs.child_inputs(conn, node))
    if not source:
        raise LLMError("this topic has nothing to write a brief from yet")
    return source


OPS["brief-preview"] = brief_preview
