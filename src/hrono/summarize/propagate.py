"""The ``propagate`` op (#087, T36): climb a changed topic up the tree.

The last piece of the incremental promise. After ``update`` (#085) re-places
changed chunks and dirties LEAF briefs, the upper levels are stale-blind: #068's
upper signature is its child NODE IDS, and a sticky-placed leaf keeps its id, so
a parent whose child's BRIEF changed looks fresh. ``propagate`` closes that —
for each leaf whose membership changed it judges the new content against the
stored brief (best-of-3, judge role via #057, OUTSIDE the #008 lock), and on a
material verdict marks ancestor briefs stale up the path (bounded by D_MAX),
bumping a per-tree drift counter that feeds the settle trigger (T39).

IDEMPOTENT PER MEMBER SET (#110): a judged leaf records the signature it was
judged against, so a reclaimed re-run of the same job re-issues no completions,
writes no second audit row and bumps no drift — while a leaf whose membership
genuinely changes afterwards is selected again. The drift bump needs no second
guard of its own: ``_bump_drift`` is reachable only through that selection.

MARKS ONLY: it never regenerates a brief. A later ``brief``/``brief-upper`` pass
regenerates exactly the marked-stale ancestors (selectively, via #064). Every
judged topic and every propagate/skip decision is written to ``update_log`` —
the audit trail the dashboard reads. Constants are baked (D_MAX 5, best-of-3).
"""

from __future__ import annotations

import sqlite3
import string
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from hrono.db.update_log import record
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
_VERDICTS = frozenset(_RANK)
_RETRIES = 1  # one re-ask per panel member before it abstains
_JUDGE_MAX_TOKENS = 16  # a verdict is one word; prose replies stay cheap


@dataclass(frozen=True)
class _Topic:
    node_id: int
    source: str  # the leaf's new content (member condensations)
    summary: str  # its stored brief text
    signature: str  # the member set being judged (#110's re-run marker)


def propagate(
    job: Job,
    context: JobContext,
    *,
    client: Completion | None = None,
) -> Mapping[str, object]:
    """Judge each changed leaf and mark its ancestors stale on drift."""
    tree = job.tree or _DEFAULT_TREE
    with context.database.connect() as conn:
        model = resolve_text_model(conn, job.scope)
        _prompt_name, template = resolve_prompt(conn, "judge")
        topics = _changed_leaves(conn, tree, str(model["name"]))
    if not topics:
        return _outcome(())

    completion = client if client is not None else _default_client(context)
    verdicts = [
        (topic, _judge(completion, model, template, topic)) for topic in topics
    ]

    with context.database.write() as conn:
        for topic, verdict in verdicts:
            _record(conn, tree, topic, verdict)
    return _outcome(tuple(verdict for _topic, verdict in verdicts))


def _outcome(verdicts: Sequence[str | None]) -> Mapping[str, object]:
    """What this run did, for the operator rather than the audit table (#132).

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
            continue  # already judged at this exact member set (#110)
        source = "\n\n".join(
            briefs.member_condensations(conn, node_id, model_name)
        )
        topics.append(_Topic(node_id, source, brief["text"], signature))
    return tuple(topics)


def _judge(
    completion: Completion,
    model: dict[str, object],
    template: str,
    topic: _Topic,
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
        for vote in (_vote(completion, request) for _ in range(BEST_OF))
        if vote is not None
    )
    return _majority(votes) if votes else None


def _vote(completion: Completion, request: CompletionRequest) -> str | None:
    """One panel member, re-asked once; ``None`` rather than a guessed verdict.

    Abstaining costs a vote, defaulting to ``none`` costs the cascade: a false
    ``none`` silently suppresses a real climb, which is the dangerous direction.
    """
    for _ in range(1 + _RETRIES):
        verdict = _verdict(completion.complete(request).text)
        if verdict is not None:
            return verdict
    return None


def _verdict(text: str) -> str | None:
    """The reply's LEADING word, if it is a verdict at all.

    The prompt asks for one word and the model answers in prose half the time
    (F33). Substring matching over prose reads the prompt's own vocabulary back:
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
