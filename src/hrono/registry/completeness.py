"""What the registry still lacks for a build to run, said before one is tried.

Settings listed config and never said whether it was enough (#210): a role with
no model, or a model whose connection had been deleted, surfaced as a failed
run minutes after it started. Every check here asks the SAME resolver the
stages ask (`resolve_text_model`, `resolve_embedding_model`, `resolve_prompt`),
so the page reports exactly the refusal the run would have met — including
"two models claim this role", which is as fatal as none.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass

from hrono.embed.model import resolve_embedding_model
from hrono.embed.runner import EmbedError
from hrono.llm.client import LLMError
from hrono.registry import store
from hrono.summarize.resolve import resolve_prompt, resolve_text_model

# The writing roles a full build (`tree maintain`) resolves before its first
# stage; `judge` is asked only by an incremental sync.
BUILD_ROLES = ("condense", "brief", "brief-upper")
SYNC_ROLES = ("judge",)


@dataclass(frozen=True)
class Gap:
    """One thing missing, and the settings section that fixes it."""

    section: str
    says: str


def gaps(conn: sqlite3.Connection) -> tuple[Gap, ...]:
    """Everything a build or a sync would refuse over, in the order met."""
    found: list[Gap] = []
    if not store.list_all(conn, "sources"):
        found.append(Gap("sources", "no source is registered to read"))
    try:
        resolve_embedding_model(conn, {})
    except EmbedError as exc:
        found.append(Gap("models", f"embedding: {exc}"))
    for role in BUILD_ROLES + SYNC_ROLES:
        when = "" if role in BUILD_ROLES else " (needed by sync)"
        try:
            resolve_text_model(conn, {}, role)
        except LLMError as exc:
            found.append(Gap("models", f"role {role}{when}: {exc}"))
        try:
            resolve_prompt(conn, role)
        except LLMError as exc:
            found.append(Gap("prompts", f"role {role}{when}: {exc}"))
    found.extend(_unreachable(conn))
    return tuple(found)


def _unreachable(conn: sqlite3.Connection) -> list[Gap]:
    """Models naming a connection that is not registered."""
    known = {str(row["name"]) for row in store.list_all(conn, "connections")}
    found = []
    for row in store.list_all(conn, "models"):
        config = json.loads(row["config"])
        connection = config.get("connection")
        if connection is not None and str(connection) not in known:
            found.append(
                Gap(
                    "models",
                    f"model {config.get('name')} calls through connection "
                    f"{connection}, which is not registered",
                )
            )
    return found
