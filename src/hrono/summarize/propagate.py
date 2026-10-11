"""The ``propagate`` op: climb a changed topic up the tree.

The last piece of the incremental promise. After ``update`` re-places changed
chunks and dirties LEAF briefs, the upper levels are stale-blind: an upper
node's signature is its child NODE IDS, and a sticky-placed leaf keeps its id,
so a parent whose child's BRIEF changed looks fresh. ``propagate`` closes that —
for each leaf whose membership changed it judges the new content against the
stored brief (best-of-3, judge role, OUTSIDE the database lock), and on a
material verdict marks ancestor briefs stale up the path (bounded by D_MAX),
bumping a per-tree drift counter that feeds the settle trigger.

IDEMPOTENT PER MEMBER SET: a judged leaf records the signature it was
judged against, so a reclaimed re-run of the same job re-issues no completions,
writes no second audit row and bumps no drift — while a leaf whose membership
genuinely changes afterwards is selected again. The drift bump needs no second
guard of its own: ``_bump_drift`` is reachable only through that selection.

MARKS ONLY: it never regenerates a brief. A later ``brief``/``brief-upper`` pass
regenerates exactly the marked-stale ancestors (selectively, via brief
freshness). Every judged topic and every propagate/skip decision is written to
``update_log`` — the audit trail the dashboard reads. Constants are baked
(D_MAX 5, best-of-3).
"""

from __future__ import annotations

import json
import sqlite3
import string
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from hrono.db.update_log import record
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.llm.client import Completion, CompletionRequest
from hrono.llm.providers import client_for
from hrono.registry.collections.trees import DEFAULT_TREE
from hrono.summarize import briefs, spend
from hrono.summarize.resolve import (
    producer_model_name,
    resolve_prompt,
    resolve_text_model,
)

_LEAF_LEVEL = 0
D_MAX = 5  # cap the climb at five levels above the changed leaf
BEST_OF = 3  # judge panel size; majority verdict
_RANK = {"none": 0, "minor": 1, "major": 2}
_DRIFT = {"minor": 1, "major": 2}
_VERDICTS = frozenset(_RANK)
_RETRIES = 1  # one re-ask per panel member before it abstains
_JUDGE_MAX_TOKENS = 16  # a verdict is one word; prose replies stay cheap


@dataclass(frozen=True)
class _Topic:
    node_id: int
    source: str  # the change: condensations added or changed, and removed
    summary: str  # its stored brief text
    signature: str  # the member set being judged (the re-run marker)


def propagate(
    job: Job,
    context: JobContext,
    *,
    client: Completion | None = None,
) -> Mapping[str, object]:
    """Judge each changed leaf and mark its ancestors stale on drift."""
    tree = job.tree or DEFAULT_TREE
    with context.database.connect() as conn:
        model = resolve_text_model(conn, job.scope, "judge")
        _prompt_name, template = resolve_prompt(conn, "judge")
        # the judge reads what CONDENSE produced, not what the judge model is
        # called — the same producer rule `brief` follows.
        topics = _changed_leaves(
            conn, tree, producer_model_name(conn, job.scope, "condense")
        )
    if not topics:
        return _outcome(())

    completion = client_for(context, model, "judge", client=client)
    spent: list[tuple[int, int]] = []
    verdicts = [
        (topic, _judge(completion, model, template, topic, spent))
        for topic in topics
    ]

    with context.database.write() as conn:
        for topic, verdict in verdicts:
            _record(conn, tree, topic, verdict)
    return _outcome(tuple(verdict for _topic, verdict in verdicts), spent)


def _outcome(
    verdicts: Sequence[str | None],
    spent: Sequence[tuple[int, int]] = (),
) -> Mapping[str, object]:
    """What this run did, for the operator rather than the audit table.

    ``abstained`` is the count that matters: those topics CHANGED and were not
    judged, so their ancestors were correctly left unmarked and a stale brief
    is still being served. ``incomplete`` is the one field a reader has to
    check to know the job did less than it was asked.
    """
    abstained = sum(1 for verdict in verdicts if verdict is None)
    return {
        "judged": len(verdicts) - abstained,
        "propagated": sum(1 for v in verdicts if v is not None and v != "none"),
        "skipped": sum(1 for v in verdicts if v == "none"),
        "abstained": abstained,
        "incomplete": abstained > 0,
        **({"tokens": tokens} if (tokens := spend.counts(spent)) else {}),
    }


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
        signature = briefs.member_signature(conn, node_id)
        if signature == brief["member_signature"]:
            continue
        if signature == brief["judged_signature"]:
            continue  # already judged at this exact member set
        source = _change(conn, node_id, model_name, brief["members"])
        topics.append(_Topic(node_id, source, brief["text"], signature))
    return tuple(topics)


def _change(
    conn: sqlite3.Connection, node_id: int, model_name: str, stored: object
) -> str:
    """What changed in a leaf since its brief, as the judge reads it.

    The research judge was shown the summary and the CHANGE, not the whole
    topic: asked about everything, a judge re-reviews the summary instead of
    the edit. A member is a file version (its URI), so a changed file reads
    as its new version added and its old one removed. A brief that recorded
    no members falls back to the whole current content.
    """
    now = briefs.reduce_input(conn, node_id, model_name)
    before = set(json.loads(stored)) if isinstance(stored, str) else set()
    if not before:
        return now.rendered
    current = set(now.uris)
    added = [
        (label, text)
        for label, text, uri in zip(
            now.labels,
            now.texts,
            _row_uris(conn, node_id, model_name),
            strict=True,
        )
        if uri not in before
    ]
    gone = sorted(before - current)
    removed = conn.execute(
        "SELECT s.path AS path, d.text AS text FROM sections s "
        "JOIN condensations d ON d.content_hash = s.content_hash "
        "AND d.model_name = ? "
        "WHERE s.uri IN (SELECT value FROM json_each(?)) ORDER BY s.uri, s.id",
        (model_name, json.dumps(gone)),
    ).fetchall()
    parts = []
    if added:
        parts.append("ADDED OR CHANGED:\n\n" + briefs.labeled(added))
    if removed:
        parts.append(
            "REMOVED:\n\n"
            + briefs.labeled((row["path"], row["text"]) for row in removed)
        )
    return "\n\n".join(parts) or now.rendered


def _row_uris(
    conn: sqlite3.Connection, node_id: int, model_name: str
) -> list[str]:
    """Each reduce-input row's URI, in the order ``reduce_input`` reads them."""
    return [
        row["uri"]
        for row in conn.execute(
            "SELECT s.uri AS uri FROM node_members m "
            "JOIN sections s ON s.id = m.section_id "
            "JOIN condensations d ON d.content_hash = s.content_hash "
            "AND d.model_name = ? WHERE m.node_id = ? ORDER BY s.uri, s.id",
            (model_name, node_id),
        )
    ]


def _judge(
    completion: Completion,
    model: dict[str, object],
    template: str,
    topic: _Topic,
    spent: list[tuple[int, int]],
) -> str | None:
    """The panel's majority verdict, or ``None`` if every member abstained."""
    content = template.replace("{source}", topic.source).replace(
        "{summary}", topic.summary
    )
    request = CompletionRequest(
        model=_capped(model), system="", content=content
    )
    votes = tuple(
        vote
        for vote in (_vote(completion, request, spent) for _ in range(BEST_OF))
        if vote is not None
    )
    return _majority(votes) if votes else None


def _vote(
    completion: Completion,
    request: CompletionRequest,
    spent: list[tuple[int, int]],
) -> str | None:
    """One panel member, re-asked once; ``None`` rather than a guessed verdict.

    Abstaining costs a vote, defaulting to ``none`` costs the cascade: a false
    ``none`` silently suppresses a real climb, which is the dangerous direction.

    ``spent`` collects what each attempt cost, retries and abstentions
    included — this op issues BEST_OF votes per changed leaf and re-asks on a
    bad reply, so it is the most expensive stage in a run and must report what
    it spends.
    """
    for _ in range(1 + _RETRIES):
        result = completion.complete(request)
        spent.append((result.usage.input_tokens, result.usage.output_tokens))
        verdict = _verdict(result.text)
        if verdict is not None:
            return verdict
    return None


def _verdict(text: str) -> str | None:
    """The reply's LEADING word, if it is a verdict at all.

    The prompt asks for one word and the model answers in prose half the time.
    Substring matching over prose reads the prompt's own vocabulary back:
    "none - not a major change" scores major. The first word is the answer; the
    rest is explanation.
    """
    head = text.strip().split(maxsplit=1)
    if not head:
        return None
    word = head[0].strip(string.punctuation).lower()
    return word if word in _VERDICTS else None


def _capped(model: dict[str, object]) -> dict[str, object]:
    """The judge's model with a verdict-sized output cap."""
    params = model.get("params")
    base = dict(params) if isinstance(params, dict) else {}
    return {**model, "params": {**base, "max_tokens": _JUDGE_MAX_TOKENS}}


def _majority(verdicts: Sequence[str]) -> str:
    ranked = sorted(verdicts, key=lambda v: _RANK[v])
    return ranked[len(ranked) // 2]


def _record(
    conn: sqlite3.Connection, tree: str, topic: _Topic, verdict: str | None
) -> None:
    if verdict is None:  # the whole panel abstained: loud, not silent
        record(conn, tree, topic.node_id, "unparseable", "abstained")
        return  # unjudged, so a re-run must try again: no marker
    briefs.mark_judged(conn, topic.node_id, topic.signature)
    if verdict == "none":
        record(conn, tree, topic.node_id, verdict, "skipped")
        return
    climbed_to = _climb(conn, topic.node_id)
    _bump_drift(conn, tree, _DRIFT[verdict])
    record(conn, tree, topic.node_id, verdict, "propagated", climbed_to)


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


OPS["propagate"] = propagate
