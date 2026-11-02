"""The insights pass: one review of a topic's subtree, then one extend call.

A strong model reviews the topic read-only on the lookups (its briefs, the
condensations and the source under it, nothing outside), and returns findings:
the rules no single section states, the siblings that differ, the wrong
statements of the cheaper brief. A second call, with no tools, writes them into
the topic's brief in place. The cheaper brief stays as the previous version
(`brief_versions`, reason 'insights', the pass that replaced it).

What decides whether a pass runs is `insights.due` (the counter and the root's
rule); this module runs it. A review that fails to finish (the turn cap, an
answer that is not findings) stores nothing and says why in the log and in the
job's outcome, and the topic is due again next time. A provider error stops the
run, as it does everywhere else, naming the topic.

A pinned brief is never overwritten: its findings are stored and the pass is
marked skipped. The pin is checked when the brief would be written, not before
the review, so the person still sees what the review found.

The extended brief keeps the cheaper brief's provenance (model, prompt,
signature): freshness is judged against what the brief-upper role would write,
so a later `brief-upper` leaves the extended brief alone until the topic's
parts change, when it is written again and the topic is due a new pass.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from hrono import naming, pins
from hrono.jobs.ops import JobContext
from hrono.llm.client import (
    Completion,
    CompletionRequest,
    LLMError,
    Unfinished,
)
from hrono.llm.providers import client_for
from hrono.recall.brief_passages import store_brief
from hrono.registry import store
from hrono.registry.collections.trees import INSIGHTS_THRESHOLD
from hrono.summarize import briefs, insights, lookup, pool, spend
from hrono.summarize.resolve import (
    INSIGHTS_ROLE,
    producer_model_name,
    resolve_prompt,
    resolve_text_model,
)
from hrono.summarize.shape import answer

_logger = logging.getLogger("hrono.insights")

REVIEW_ROLE = "insights-review"
EXTEND_ROLE = "insights-extend"
MOST_LOOKUPS = 60  # the review's turn cap: 34-52 were used in the measurements
MOST_FINDINGS = 15
INDEX_CHARS = 60_000  # the one-line index of a very large area is cut to this
_LINE_CHARS = (80, 380)  # each index line, at least and at most


@dataclass(frozen=True)
class Finding:
    statement: str
    angle: str = ""
    why: str = ""
    evidence: tuple[dict[str, str], ...] = ()
    placement: str = ""
    confidence: str = ""


@dataclass(frozen=True)
class Review:
    findings: tuple[Finding, ...]
    dropped: tuple[str, ...] = ()
    looked: str = ""


@dataclass
class Outcome:
    reviews: int = 0
    extends: int = 0
    findings: int = 0
    failed: list[str] = field(default_factory=list)
    usage: list[spend.Usage] = field(default_factory=list)
    note: str = ""

    def as_dict(self) -> dict[str, object]:
        out: dict[str, object] = {
            "reviews": self.reviews,
            "extends": self.extends,
            "findings": self.findings,
        }
        if self.failed:
            out["failed"] = self.failed
        if self.note:
            out["note"] = self.note
        if (tokens := spend.counts(self.usage)) is not None:
            out["tokens"] = tokens
        return out


def parse(text: str) -> Review:
    """The review's JSON answer as findings, or ``Unfinished`` when it is not.

    A model that wrote its answer in a code fence or after a sentence is
    still answering; one that wrote no object with a list of findings is
    not, and storing nothing is the answer to that.
    """
    body = _answer_object(text)
    if body is None:
        raise Unfinished("the review's answer was not a list of findings")
    found = [
        _finding(one)
        for one in body["findings"][:MOST_FINDINGS]
        if isinstance(one, dict) and str(one.get("statement", "")).strip()
    ]
    dropped = body.get("dropped")
    return Review(
        tuple(found),
        tuple(str(d) for d in dropped) if isinstance(dropped, list) else (),
        str(body.get("looked") or ""),
    )


def _answer_object(text: str) -> dict[str, object] | None:
    """The first JSON object in ``text`` that holds a list of findings.

    Tried at each brace, so a brace in the prose around it (a note on
    ``{config}``) does not lose a review that was paid for.
    """
    decoder = json.JSONDecoder()
    start = text.find("{")
    while start >= 0:
        try:
            body, _ = decoder.raw_decode(text, start)
        except ValueError:
            body = None
        if isinstance(body, dict) and isinstance(body.get("findings"), list):
            return body
        start = text.find("{", start + 1)
    return None


def _finding(one: dict[str, object]) -> Finding:
    evidence = one.get("evidence")
    return Finding(
        statement=str(one["statement"]).strip(),
        angle=str(one.get("angle") or ""),
        why=str(one.get("why") or ""),
        evidence=tuple(
            {k: str(v) for k, v in item.items()}
            if isinstance(item, dict)
            else {"file": str(item)}
            for item in (evidence if isinstance(evidence, list) else [])
        ),
        placement=str(one.get("placement") or ""),
        confidence=str(one.get("confidence") or ""),
    )


def render_findings(findings: tuple[Finding, ...]) -> str:
    """The findings as the extend call reads them."""
    out = []
    for number, one in enumerate(findings, start=1):
        seen = "; ".join(
            f"{e.get('file', '')}"
            + (f":{e['lines']}" if e.get("lines") else "")
            for e in one.evidence
        )
        out.append(
            f"{number}. {one.statement}\n   why it matters: {one.why}\n"
            f"   evidence: {seen}\n   place it: {one.placement}\n"
            f"   confidence: {one.confidence}"
        )
    return "\n".join(out)


def fill(template: str, **values: str) -> str:
    """``template`` with each ``{name}`` replaced, in one pass.

    One pass, so a brief that happens to contain ``{index}`` is not filled
    twice.
    """
    return re.sub(
        r"\{(" + "|".join(values) + r")\}", lambda m: values[m[1]], template
    )


class Area:
    """What a pass over one topic may read, and what it is told up front."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        tree: str,
        node: int,
        condense_model: str,
    ) -> None:
        below = _below(conn, node)
        leaves = [n for n in below if not _children(conn, n)]
        sections = {
            int(r["section_id"]): f"{r['source']}/{r['path']}"
            for n in leaves
            for r in conn.execute(
                "SELECT m.section_id, s.source, s.path FROM node_members m "
                "JOIN sections s ON s.id = m.section_id WHERE m.node_id = ?",
                (n,),
            )
        }
        names = naming.names(conn, below)
        held = {
            n: str(r["text"])
            for n in below
            if (r := briefs.get(conn, n)) is not None
        }
        paths = {
            n: f"{lookup.BRIEF}{naming.slug(names[n])}-{n}.md" for n in held
        }
        found = lookup.files(conn, tree, condense_model, only=set(sections))
        self.files = lookup.Files(
            {**found.texts, **{paths[n]: held[n] for n in held}}
        )
        self.brief = str(briefs.get(conn, node)["text"])  # type: ignore[index]
        files_of: dict[int, list[str]] = {}
        for n in leaves:
            files_of[n] = sorted(
                {
                    sections[int(r["section_id"])]
                    for r in conn.execute(
                        "SELECT section_id FROM node_members WHERE node_id = ?",
                        (n,),
                    )
                }
            )
        self.index = _index(below, names, held, paths, files_of)


def _children(conn: sqlite3.Connection, node: int) -> list[int]:
    return [
        int(r["child_id"])
        for r in conn.execute(
            "SELECT child_id FROM node_children WHERE parent_id = ? "
            "ORDER BY child_id",
            (node,),
        )
    ]


def _below(conn: sqlite3.Connection, node: int) -> list[int]:
    """Every topic under ``node``, nearest first, not ``node`` itself."""
    seen = {node}
    order: list[int] = []
    queue = [node]
    while queue:
        for child in _children(conn, queue.pop(0)):
            if child not in seen:
                seen.add(child)
                order.append(child)
                queue.append(child)
    return order


def _index(
    below: list[int],
    names: dict[int, str],
    held: dict[int, str],
    paths: dict[int, str],
    files_of: dict[int, list[str]],
) -> str:
    """One line per topic: its name, what it is, and its files."""
    least, most = _LINE_CHARS
    each = max(least, min(most, INDEX_CHARS // max(1, len(below))))
    lines = []
    for n in below:
        text = held.get(n, "")
        first = next((ln for ln in text.splitlines() if ln.strip()), "")
        said = naming.sentence(naming.unframe(first), each)
        where = ", ".join(files_of.get(n, [])[:3])
        line = f"- {names[n]} ({paths.get(n, '-')}): {said}"
        lines.append(line + (f" | files: {where}" if where else ""))
    return "\n".join(lines)[: INDEX_CHARS + len(below) * 20]


@dataclass(frozen=True)
class Reviewed:
    node: int
    name: str
    review: Review | None  # None: the review did not finish
    why_not: str
    extended: str
    flagged: str
    usage: tuple[tuple[int, int], ...]


def run(
    context: JobContext,
    tree: str,
    *,
    levels: range | list[int],
    root: bool,
    client: Completion | None = None,
    rebrief: Callable[[int], None] | None = None,
) -> dict[str, object]:
    """Run the passes the tree's counter selects, level by level.

    ``root`` says the top level is final, so its topic gets the root's pass.
    After a level's passes, the parents of the topics that were extended are
    briefed again from the extended briefs (``rebrief(level)``), before the
    next level is counted.
    """
    outcome = Outcome()
    with context.database.connect() as conn:
        row = store.get(conn, "trees", tree)
        config = json.loads(row["config"]) if row is not None else {}
    if not config.get("insights"):
        return {}
    threshold = int(config.get("insights_threshold") or INSIGHTS_THRESHOLD)
    with context.database.connect() as conn:
        try:
            model = resolve_text_model(conn, {}, INSIGHTS_ROLE)
            _, review_template = resolve_prompt(conn, REVIEW_ROLE)
            _, extend_template = resolve_prompt(conn, EXTEND_ROLE)
            condense_model = producer_model_name(conn, {}, "condense")
        except LLMError as exc:
            outcome.note = str(exc)
            _logger.warning("insights: nothing ran: %s", exc)
            return outcome.as_dict()
    completion = client_for(context, model, INSIGHTS_ROLE, client=client)
    model_name = str(model["name"])
    for level in levels:
        with context.database.connect() as conn:
            chosen = [
                p.node
                for p in insights.due(conn, tree, level, threshold, root)
                if briefs.get(conn, p.node) is not None
            ]
        if not chosen:
            continue
        done = pool.mapped(
            chosen,
            lambda node: _review(
                context,
                tree,
                node,
                condense_model,
                completion,
                model,
                review_template,
                extend_template,
            ),
            lambda node, made: _keep(context, node, made, model_name, outcome),
            workers=pool.width(),
            proceed=lambda: True,
            named=lambda node: f"topic {node}",
        )
        applied = [m.node for m in done if m.extended]
        if applied and rebrief is not None:
            _rebrief_parents(context, applied, rebrief)
    return outcome.as_dict()


def _review(
    context: JobContext,
    tree: str,
    node: int,
    condense_model: str,
    completion: Completion,
    model: dict[str, object],
    review_template: str,
    extend_template: str,
) -> Reviewed:
    with context.database.connect() as conn:
        area = Area(conn, tree, node, condense_model)
        name = naming.name(conn, node)
    box = lookup.toolbox(area.files, most=MOST_LOOKUPS)
    asked = fill(review_template, brief=area.brief, index=area.index)
    usage: list[tuple[int, int]] = []
    try:
        first = completion.complete(
            CompletionRequest(model=model, system="", content=asked, tools=box)
        )
        usage.append((first.usage.input_tokens, first.usage.output_tokens))
        review = parse(first.text)
    except Unfinished as exc:
        return Reviewed(node, name, None, str(exc), "", "", tuple(usage))
    if not review.findings:
        return Reviewed(node, name, review, "no findings", "", "", tuple(usage))
    with context.database.connect() as conn:
        if pins.is_pinned(conn, pins.BRIEF, node):
            # the brief is a person's: no call to write over it
            return Reviewed(node, name, review, "pinned", "", "", tuple(usage))
    rendered = fill(
        extend_template,
        brief=area.brief,
        findings=render_findings(review.findings),
    )
    try:
        written, flagged = answer(
            completion,
            CompletionRequest(model=model, system="", content=rendered),
        )
    except Unfinished as exc:
        return Reviewed(
            node,
            name,
            review,
            f"the extend call failed: {exc}",
            "",
            "",
            tuple(usage),
        )
    usage.append((written.usage.input_tokens, written.usage.output_tokens))
    why = f"the extend call gave no brief ({flagged})" if flagged else ""
    return Reviewed(
        node,
        name,
        review,
        why,
        "" if flagged else written.text,
        flagged,
        tuple(usage),
    )


def _keep(
    context: JobContext,
    node: int,
    made: Reviewed,
    model_name: str,
    outcome: Outcome,
) -> None:
    outcome.usage.extend(made.usage)
    if made.review is None:
        outcome.failed.append(f"{made.name}: {made.why_not}")
        _logger.warning(
            "insights: no review stored for %s (topic %d): %s",
            made.name,
            node,
            made.why_not,
        )
        return
    with context.database.write() as conn:
        pinned = pins.is_pinned(conn, pins.BRIEF, node)
        stored = conn.execute(
            "SELECT * FROM briefs WHERE node_id = ?", (node,)
        ).fetchone()
        skipped = "pinned" if pinned else made.why_not
        apply = bool(made.extended) and not pinned and stored is not None
        pass_id = _store_pass(conn, node, made, model_name, skipped)
        if apply:
            briefs.upsert(
                conn,
                node,
                made.extended,
                model_name=stored["model_name"],
                prompt_name=stored["prompt_name"],
                prompt_hash=stored["prompt_hash"],
                member_signature=stored["member_signature"],
                input_tokens=stored["input_tokens"],
                output_tokens=stored["output_tokens"],
                model_fingerprint=stored["model_fingerprint"],
                unfaithful=stored["unfaithful"],
                flagged=stored["flagged"],
                members=stored["members"],
                source_model=stored["source_model"],
                reason="insights",
                pass_id=pass_id,
            )
            store_brief(conn, node, made.extended, stored["member_signature"])
        # after the brief, so the brief the pass left is covered by it
        conn.execute(
            "UPDATE insights_passes SET passed_at = ? WHERE id = ?",
            (datetime.now(UTC).isoformat(), pass_id),
        )
    outcome.reviews += 1
    outcome.findings += len(made.review.findings)
    outcome.extends += 1 if apply else 0
    if skipped:
        _logger.info(
            "insights: %s (topic %d) kept: %s", made.name, node, skipped
        )


def _store_pass(
    conn: sqlite3.Connection,
    node: int,
    made: Reviewed,
    model_name: str,
    skipped: str,
) -> int:
    assert made.review is not None
    cursor = conn.execute(
        "INSERT INTO insights_passes(node_id, passed_at, model_name, version, "
        "skipped, dropped, looked) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            node,
            datetime.now(UTC).isoformat(),
            model_name,
            briefs.member_signature(conn, node),
            skipped,
            json.dumps(list(made.review.dropped)),
            made.review.looked,
        ),
    )
    pass_id = int(cursor.lastrowid or 0)
    for position, one in enumerate(made.review.findings):
        conn.execute(
            "INSERT INTO insights_findings(pass_id, position, statement, "
            "angle, why, evidence, placement, confidence) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                pass_id,
                position,
                one.statement,
                one.angle,
                one.why,
                json.dumps(list(one.evidence)),
                one.placement,
                one.confidence,
            ),
        )
    return pass_id


def _rebrief_parents(
    context: JobContext, nodes: list[int], rebrief: Callable[[int], None]
) -> None:
    """Write each parent of an extended topic again, from the extended brief."""
    with context.database.write() as conn:
        parents = {
            int(r["parent_id"]): int(r["level"])
            for n in nodes
            for r in conn.execute(
                "SELECT c.parent_id, p.level FROM node_children c "
                "JOIN nodes p ON p.id = c.parent_id WHERE c.child_id = ?",
                (n,),
            )
        }
        for parent in parents:
            briefs.mark_stale(conn, parent)
    for level in sorted(set(parents.values())):
        rebrief(level)
