"""What the next sync will rewrite, said before it runs.

A tree built by an older hrono is, to the new one, a tree whose briefs were
written by another prompt and whose sections sit where their raw text put them,
not their condensations. Nothing in it is wrong or flagged, and the first sync
rewrites a great deal of it, one time, at the admin's cost. This reads the same
facts that sync reads (the prompt and model it will write with, the vectors it
will place by) and counts the briefs it will write again, so the Home page and
Health can say so, and what it costs, before the button is pressed.

It is live, a few queries over the briefs, because the stored health report
only exists after a sync has run and this question is asked before one.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from hrono import pins
from hrono.cluster import store as cluster_store
from hrono.cluster.blend import condense_model
from hrono.cluster.repair import MAX_CAP
from hrono.embed.model import resolve_embedding_model
from hrono.errors import AppError, DomainError
from hrono.ingest.identity import content_hash
from hrono.llm.client import LLMError
from hrono.onboarding.estimate import provider_of, upstream_of
from hrono.registry import impact
from hrono.registry.collections.trees import looks_up
from hrono.summarize import lookup
from hrono.summarize.resolve import (
    model_fingerprint,
    resolve_prompt,
    resolve_text_model,
    template_hash,
)
from hrono.usage.prices import from_config, price_for
from hrono.usage.rollup import SUBSCRIPTION

PROMPT = "prompt"
MODEL = "model"
# a topic that splits becomes at least two
SPLIT_INTO = 2


@dataclass(frozen=True)
class Older:
    """A brief the next sync writes again, and why."""

    node_id: int
    level: int
    why: str  # PROMPT or MODEL


@dataclass(frozen=True)
class Plan:
    older: tuple[Older, ...]
    # sections whose condensation has no vector yet: placed by it from the
    # next sync on, so topics over the size cap split and sections move
    moving: int
    calls: int
    tokens: dict[str, int] | None
    usd: float | None
    # "subscription" (an estimate, never spend), "metered", or "" with no price
    billing: str

    def __bool__(self) -> bool:
        return bool(self.older or self.moving)


def plan(conn: sqlite3.Connection, tree: str) -> Plan:
    """What the next sync would rewrite in ``tree``, if nothing else changed."""
    older = _older(conn, tree)
    moving = _moving(conn, tree)
    leaves = sum(1 for one in older if one.level == 0)
    upper = len(older) - leaves
    if moving:
        split, above = _splits(conn, tree)
        leaves += SPLIT_INTO * len(split)
        upper += len(above)
    return _priced(conn, tree, older, moving, leaves, upper)


def _older(conn: sqlite3.Connection, tree: str) -> tuple[Older, ...]:
    standing: dict[bool, tuple[str, str, str]] = {}
    try:
        for leaf, role in ((True, "brief"), (False, "brief-upper")):
            model = resolve_text_model(conn, {}, role)
            _, template = resolve_prompt(conn, role)
            if leaf and looks_up(conn, tree):
                template += lookup.INSTRUCTION
            standing[leaf] = (
                template_hash(template),
                str(model["name"]),
                model_fingerprint(model),
            )
    except LLMError:
        return ()  # no model to write with: a sync could not rewrite anything
    held = pins.pinned(conn, pins.BRIEF)
    found = []
    for row in conn.execute(
        "SELECT n.id AS id, n.level AS level, b.prompt_hash AS hash, "
        "b.model_name AS model, b.model_fingerprint AS fingerprint "
        "FROM briefs b JOIN nodes n ON n.id = b.node_id "
        "WHERE n.tree = ? ORDER BY n.level, n.id",
        (tree,),
    ):
        node = int(row["id"])
        if node in held:
            continue
        prompt, model, fingerprint = standing[int(row["level"]) == 0]
        if row["hash"] != prompt:
            found.append(Older(node, int(row["level"]), PROMPT))
        elif row["model"] != model or (
            row["fingerprint"] is not None and row["fingerprint"] != fingerprint
        ):
            found.append(Older(node, int(row["level"]), MODEL))
    return tuple(found)


def _moving(conn: sqlite3.Connection, tree: str) -> int:
    """Sections in the tree whose condensation is not embedded yet."""
    condenser = condense_model(conn)
    if condenser is None:
        return 0
    try:
        model = str(resolve_embedding_model(conn, {})["name"])
    except (AppError, DomainError):
        return 0
    texts = conn.execute(
        "SELECT DISTINCT c.text AS text FROM condensations c "
        "JOIN sections s ON s.content_hash = c.content_hash "
        "JOIN node_members m ON m.section_id = s.id "
        "JOIN nodes n ON n.id = m.node_id "
        "WHERE n.tree = ? AND c.model_name = ?",
        (tree, condenser),
    ).fetchall()
    return sum(
        1
        for row in texts
        if conn.execute(
            "SELECT 1 FROM embeddings WHERE content_hash = ? "
            "AND model_name = ?",
            (content_hash(str(row["text"]).encode("utf-8")), model),
        ).fetchone()
        is None
    )


def _splits(conn: sqlite3.Connection, tree: str) -> tuple[list[int], set[int]]:
    """The bottom topics over the size cap, and every topic above them."""
    over = [
        int(row["id"])
        for row in conn.execute(
            "SELECT n.id AS id FROM nodes n JOIN node_members m "
            "ON m.node_id = n.id WHERE n.tree = ? AND n.level = 0 "
            "GROUP BY n.id HAVING COUNT(*) > ?",
            (tree, MAX_CAP),
        )
    ]
    above: set[int] = set()
    for node in over:
        parent = cluster_store.parent_of(conn, node)
        while parent is not None:
            above.add(parent)
            parent = cluster_store.parent_of(conn, parent)
    return over, above


def _priced(
    conn: sqlite3.Connection,
    tree: str,
    older: tuple[Older, ...],
    moving: int,
    leaves: int,
    upper: int,
) -> Plan:
    """Tokens from what briefs here measured, money from the price table."""
    calls = leaves + upper
    tokens: dict[str, int] | None = {"input": 0, "output": 0}
    usd: float | None = 0.0
    billing = ""
    levels = _levels(conn, tree)
    for role, count, wanted in (
        ("brief", leaves, levels[:1]),
        ("brief-upper", upper, levels[1:]),
    ):
        if not count:
            continue
        made = impact.estimate(conn, tree, wanted, count)
        if made.tokens is None or tokens is None:
            tokens = None
        else:
            tokens = {k: tokens[k] + made.tokens[k] for k in tokens}
        try:
            model = resolve_text_model(conn, {}, role)
        except LLMError:
            usd = None
            continue
        price = price_for(upstream_of(conn, model), from_config(model))
        if price is None or made.tokens is None or usd is None:
            usd = None
        else:
            usd += price.cost(made.tokens["input"], made.tokens["output"], 0, 0)
            billing = _billing(billing, provider_of(conn, model))
    return Plan(older, moving, calls, tokens, usd, billing if usd else "")


def _billing(so_far: str, provider: str) -> str:
    kind = "subscription" if provider in SUBSCRIPTION else "metered"
    return kind if so_far in ("", kind) else "mixed"


def _levels(conn: sqlite3.Connection, tree: str) -> list[int]:
    return [
        int(row["level"])
        for row in conn.execute(
            "SELECT DISTINCT level FROM nodes WHERE tree = ? ORDER BY level",
            (tree,),
        )
    ]
