"""Shared resolution for the summarisation ops: the text model and the prompt.

``condense`` and ``brief`` both need the same two lookups — which text model to
call and which role prompt to render — so the rule lives here once. The text
model is the one named in the job scope, else the one whose ``role`` matches the
calling stage (#067), else the sole ``text``-kind model; the prompt is the sole
registry prompt of the requested role. A missing or ambiguous choice raises a
clean ``LLMError`` a job leaf fails on.

A STAGE READS ANOTHER STAGE'S CACHE UNDER THE PRODUCER'S MODEL, not its own
(#067). ``brief`` reduces the condensations ``condense`` wrote, and those are
keyed by the CONDENSE model's name. While there was one text model the two names
were the same and the join matched; with a cheap condense model and a smart
brief model, briefing under its own name would find no condensations and
silently summarise nothing. ``producer_model_name`` is that lookup, and it is
the reason this module owns role resolution rather than each op doing its own.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3

from hrono.llm.client import LLMError
from hrono.registry import store as registry_store


def resolve_text_model(
    conn: sqlite3.Connection,
    scope: dict[str, object],
    role: str | None = None,
) -> dict[str, object]:
    """Return the text model for ``role`` under ``scope``, or raise LLMError.

    Three rules, in order: a model NAMED in the scope wins (an operator pinning
    one run); otherwise the model whose ``role`` matches this stage; otherwise
    the sole text model. The last is the YAGNI default and stays exact — a
    one-model install configures no roles and behaves as it always has.

    The first rule needs no branch of its own: a named scope narrows the rows to
    that one model, so everything below has a single candidate to return.
    """
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
    if role is not None:
        for_role = [c for c in text if c.get("role") == role]
        if len(for_role) > 1:
            raise LLMError(f"multiple text models for role: {role}")
        if for_role:
            return for_role[0]
    if len(text) > 1:
        raise LLMError(
            f"multiple text models — give one a role ({role})"
            if role
            else "multiple text models — name one in the scope"
        )
    return text[0]


def template_hash(template: str) -> str:
    """The provenance hash of a prompt template.

    Here rather than in one op, because the preview that says what an edit
    would make stale (#190) has to hash the way the op that will later read
    the provenance hashes. A second `sha256` call is not the same function.
    """
    return hashlib.sha256(template.encode("utf-8")).hexdigest()


def resolve_prompt(conn: sqlite3.Connection, role: str) -> tuple[str, str]:
    """Return the (name, template) of the sole prompt with ``role``."""
    configs = [
        json.loads(row["config"])
        for row in registry_store.list_all(conn, "prompts")
    ]
    matches = [c for c in configs if c.get("role") == role]
    if not matches:
        raise LLMError(f"no {role} prompt configured")
    if len(matches) > 1:
        raise LLMError(f"multiple {role} prompts configured")
    return str(matches[0]["name"]), str(matches[0]["template"])


def producer_model_name(
    conn: sqlite3.Connection, scope: dict[str, object], role: str
) -> str:
    """The model name a consumer must key ``role``'s cached output by (#067)."""
    return str(resolve_text_model(conn, scope, role)["name"])
