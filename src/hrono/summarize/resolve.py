"""Shared resolution for the summarisation ops: the text model and the prompt.

``condense`` and ``brief`` both need the same two lookups — which text model to
call and which role prompt to render — so the rule lives here once. The text
model is the sole ``text``-kind model, or the one named in the job scope (like
``embed/model``); the prompt is the sole registry prompt of the requested role.
A missing or ambiguous choice raises a clean ``LLMError`` a job leaf fails on.
"""

from __future__ import annotations

import json
import sqlite3

from hrono.llm.client import LLMError
from hrono.registry import store as registry_store


def resolve_text_model(
    conn: sqlite3.Connection, scope: dict[str, object]
) -> dict[str, object]:
    """Return the text model config for ``scope``, or raise LLMError."""
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
    if name is None and len(text) > 1:
        raise LLMError("multiple text models — name one in the scope")
    return text[0]


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
