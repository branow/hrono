"""The ``propagate`` op (#087, T36): climb a changed topic up the tree.

The last piece of the incremental promise. After ``update`` (#085) re-places
changed chunks and dirties LEAF briefs, the upper levels are stale-blind: #068's
upper signature is its child NODE IDS, and a sticky-placed leaf keeps its id, so
a parent whose child's BRIEF changed looks fresh. ``propagate`` closes that —
for each leaf whose membership changed it judges the new content against the
stored brief (best-of-3, judge role via #057, OUTSIDE the #008 lock), and on a
material verdict marks ancestor briefs stale up the path (bounded by D_MAX),
bumping a per-tree drift counter that feeds the settle trigger (T39).

MARKS ONLY: it never regenerates a brief. A later ``brief``/``brief-upper`` pass
regenerates exactly the marked-stale ancestors (selectively, via #064). Every
judged topic and every propagate/skip decision is written to ``update_log`` —
the audit trail the dashboard reads. Constants are baked (D_MAX 5, best-of-3).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import Completion, CompletionRequest
from hrono.summarize import briefs
from hrono.summarize.brief import _default_client
from hrono.summarize.resolve import resolve_prompt, resolve_text_model

_DEFAULT_TREE = "default"
_LEAF_LEVEL = 0
D_MAX = 5  # cap the climb at five levels above the changed leaf
BEST_OF = 3  # judge panel size; majority verdict
_RANK = {"none": 0, "minor": 1, "major": 2}
_DRIFT = {"minor": 1, "major": 2}


@dataclass(frozen=True)
class _Topic:
    node_id: int
    source: str  # the leaf's new content (member condensations)
    summary: str  # its stored brief text


def propagate(
    job: Job,
    context: JobContext,
    *,
    client: Completion | None = None,
) -> None:
    """Judge each changed leaf and mark its ancestors stale on drift."""
    tree = job.tree or _DEFAULT_TREE
    with context.database.connect() as conn:
        model = resolve_text_model(conn, job.scope)
        _prompt_name, template = resolve_prompt(conn, "judge")
        topics = _changed_leaves(conn, tree, str(model["name"]))
    if not topics:
        return

    completion = client if client is not None else _default_client(context)
    verdicts = [
        (topic, _judge(completion, model, template, topic)) for topic in topics
    ]

    with context.database.connect() as conn, conn:
        for topic, verdict in verdicts:
            _record(conn, tree, topic, verdict)


def _changed_leaves(
    conn: sqlite3.Connection, tree: str, model_name: str
) -> tuple[_Topic, ...]:
    """Leaf nodes whose membership changed (a stored brief, signature drift)."""
    topics: list[_Topic] = []
    for row in conn.execute(
        "SELECT id FROM nodes WHERE tree = ? AND level = ? ORDER BY id",
        (tree, _LEAF_LEVEL),
    ).fetchall():
        node_id = int(row["id"])
        brief = briefs.get(conn, node_id)
        if brief is None:
            continue
        if briefs.member_signature(conn, node_id) == brief["member_signature"]:
            continue
        source = "\n\n".join(
            briefs.member_condensations(conn, node_id, model_name)
        )
        topics.append(_Topic(node_id, source, brief["text"]))
    return tuple(topics)


def _judge(
    completion: Completion,
    model: dict[str, object],
    template: str,
    topic: _Topic,
) -> str:
    content = template.replace("{source}", topic.source).replace(
        "{summary}", topic.summary
    )
    request = CompletionRequest(model=model, system="", content=content)
    verdicts = [
        _verdict(completion.complete(request).text) for _ in range(BEST_OF)
    ]
    return _majority(verdicts)


def _verdict(text: str) -> str:
    lowered = text.lower()
    if "major" in lowered:
        return "major"
    if "minor" in lowered:
        return "minor"
    return "none"


def _majority(verdicts: Sequence[str]) -> str:
    ranked = sorted(verdicts, key=lambda v: _RANK[v])
    return ranked[len(ranked) // 2]


def _record(
    conn: sqlite3.Connection, tree: str, topic: _Topic, verdict: str
) -> None:
    if verdict == "none":
        _log(conn, tree, topic.node_id, verdict, "skipped", None)
        return
    climbed_to = _climb(conn, topic.node_id)
    _bump_drift(conn, tree, _DRIFT[verdict])
    _log(conn, tree, topic.node_id, verdict, "propagated", climbed_to)


def _climb(conn: sqlite3.Connection, node_id: int) -> int | None:
    """Mark ancestor briefs stale up to D_MAX levels; return the top level."""
    current = node_id
    climbed_to: int | None = None
    for _ in range(D_MAX):
        parent = _parent_of(conn, current)
        if parent is None:
            break
        briefs.mark_stale(conn, parent)
        climbed_to = _level_of(conn, parent)
        current = parent
    return climbed_to


def _parent_of(conn: sqlite3.Connection, node_id: int) -> int | None:
    row = conn.execute(
        "SELECT parent_id FROM node_children WHERE child_id = ?", (node_id,)
    ).fetchone()
    return int(row["parent_id"]) if row is not None else None


def _level_of(conn: sqlite3.Connection, node_id: int) -> int:
    row = conn.execute(
        "SELECT level FROM nodes WHERE id = ?", (node_id,)
    ).fetchone()
    return int(row["level"])


def _bump_drift(conn: sqlite3.Connection, tree: str, amount: int) -> None:
    conn.execute(
        "INSERT INTO tree_batch(tree, batch, drift) VALUES (?, 0, ?) "
        "ON CONFLICT(tree) DO UPDATE SET drift = drift + ?",
        (tree, amount, amount),
    )


def _log(
    conn: sqlite3.Connection,
    tree: str,
    node_id: int,
    verdict: str,
    action: str,
    climbed_to: int | None,
) -> None:
    conn.execute(
        "INSERT INTO update_log(tree, node_id, verdict, action, climbed_to, "
        "created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (tree, node_id, verdict, action, climbed_to, _now()),
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


OPS["propagate"] = propagate
