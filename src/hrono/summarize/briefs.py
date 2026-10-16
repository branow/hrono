"""Persist and read back node briefs, and gather the inputs a brief reduces.

A brief is one row per node carrying the summary text (member reference URIs
already baked in by the op), the provenance the cost API reads back (model,
prompt name + template hash, token usage), the member-set signature it was
written against, and its timestamp. ``stale_or_missing`` drives incremental
regeneration: a node needs a brief when it has none, or when its members or its
prompt/model have changed since the brief was written. The gather
helpers join node membership to the sections' condensations (the LLM input) and
to the section URIs (the mechanical references).
"""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from hrono import pins
from hrono.llm.client import LLMError
from hrono.summarize import shape
from hrono.summarize.resolve import producer_model_name


def member_signature(conn: sqlite3.Connection, node_id: int) -> str:
    """Return a stable content-derived hash of a node's members.

    Leaf members sign over their sections' CONTENT HASHES, not section ids, so
    the signature survives a re-split that re-mints section ids for unchanged
    content — this is what lets the fresh-brief skip actually fire through a
    rebuild. Upper members sign over their child node ids (stable once the level
    below is) and over what ``outside`` gives them. Tokens are prefixed so a
    content hash and node id never collide.
    """
    content_hashes = [
        row["content_hash"]
        for row in conn.execute(
            "SELECT s.content_hash AS content_hash FROM node_members m "
            "JOIN sections s ON s.id = m.section_id WHERE m.node_id = ? "
            "ORDER BY s.content_hash",
            (node_id,),
        ).fetchall()
    ]
    if content_hashes:
        tokens = [f"c{h}" for h in sorted(content_hashes)]
    else:
        children = [
            int(row["child_id"])
            for row in conn.execute(
                "SELECT child_id FROM node_children WHERE parent_id = ? "
                "ORDER BY child_id",
                (node_id,),
            ).fetchall()
        ]
        tokens = [f"n{i}" for i in children]
        # what the parts elsewhere say is input too: a changed relation or
        # outside brief rewrites the area that reads it
        if beyond := outside(conn, node_id):
            tokens.append("o" + hashlib.sha256(beyond.encode()).hexdigest())
    return hashlib.sha256(",".join(tokens).encode("utf-8")).hexdigest()


def _is_fresh(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    member_sig: str,
    prompt_hash: str,
    model_name: str,
    model_fingerprint: str | None = None,
) -> bool:
    """Whether a brief still stands. The ONE place freshness is decided.

    The fingerprint is what the model NAME cannot say: repointing
    `sonnet` at another upstream model leaves the name identical and every
    word different. A brief written before the column existed carries NULL,
    and NULL is not staleness — see `0034_brief_model_fingerprint.sql`.

    A brief that was written, retried and stored flagged is not re-paid while
    nothing it was written from changes: the member signature, prompt
    hash and model checks below are the "until" — it stays listed, and it is
    rewritten once one of them moves.
    """
    return (
        not row["stale"]
        and not _rewritable(conn, row)
        and row["member_signature"] == member_sig
        and row["prompt_hash"] == prompt_hash
        and row["model_name"] == model_name
        and (
            model_fingerprint is None
            or row["model_fingerprint"] is None
            or row["model_fingerprint"] == model_fingerprint
        )
    )


def _rewritable(conn: sqlite3.Connection, row: sqlite3.Row) -> bool:
    """Whether a stored brief is worth another call for what it says.

    A stored ``echoes-the-prompt`` flag the gate STILL raises is settled: the
    model was asked twice and echoed twice, and the same members, prompt and
    model will echo again. A talk-back is retried, and so is a
    flag the gate would no longer raise.
    """
    if not unusable(conn, row):
        return False
    return not (
        row["flagged"] == shape.ECHOES
        and refusal(conn, row["node_id"], "", row["text"], row["template"])
        == shape.ECHOES
    )


# How many replaced briefs a topic keeps; the oldest beyond this are dropped.
KEEP_VERSIONS = 5

# The template of the prompt a brief was written with, as a column: a query
# over ``briefs b`` selects ``{TEMPLATE} AS template`` and hands it to
# ``refusal``, which cannot tell an echo of the prompt without it.
TEMPLATE = (
    "(SELECT json_extract(p.config, '$.template') FROM registry p "
    "WHERE p.collection = 'prompts' AND p.name = b.prompt_name)"
)


def unusable(conn: sqlite3.Connection, row: sqlite3.Row) -> str:
    """Why a stored brief is not a brief, or "" when it is one.

    The flag stored when it was written, or the CURRENT gate's verdict on its
    text — so a brief stored before a rule existed is caught by it too, and
    one that is not a brief is never fresh: the next brief pass rewrites it,
    and only it. A settled ``echoes-the-prompt`` is the exception: it is listed
    but stays until its members, prompt or model change.
    """
    return refusal(
        conn, row["node_id"], row["flagged"], row["text"], row["template"]
    )


def refusal(
    conn: sqlite3.Connection,
    node_id: int,
    flagged: object,
    text: object,
    template: object,
) -> str:
    """``unusable`` over the columns, for a caller holding just those.

    A node's material is read only for a text that echoes the prompt without
    it: that is rare, and a page of nodes must not read the corpus.
    """
    words = str(text or "")
    return (
        str(flagged or "")
        or shape.unusable(words)
        or _echo(conn, node_id, words, template)
    )


def _echo(
    conn: sqlite3.Connection, node_id: int, text: str, template: object
) -> str:
    if not shape.echoes(text, template):
        return ""
    return shape.echoes(text, template, material(conn, node_id))


def material(conn: sqlite3.Connection, node_id: int) -> str:
    """What a node's brief was written from: its member condensations by the
    condense model, or its child briefs. The words a brief may share with its
    prompt.

    Exactly the reduce input ``brief`` gates against: a condensation a
    previous condense model left in the cache is not part of it, or a settled
    echo would read as a different one and be re-paid.
    """
    source = condense_model(conn, node_id)
    inputs = reduce_input(conn, node_id, source)
    if inputs.texts:
        return inputs.rendered
    return labeled(child_inputs(conn, node_id))


def condense_model(conn: sqlite3.Connection, node_id: int) -> str:
    """The condense model a brief was written from: the one it recorded, else
    the install's own (a scoped job's choice is not visible at read time)."""
    row = conn.execute(
        "SELECT source_model FROM briefs WHERE node_id = ?", (node_id,)
    ).fetchone()
    if row is not None and row["source_model"]:
        return str(row["source_model"])
    try:
        return producer_model_name(conn, {}, "condense")
    except LLMError:
        return ""


def unusable_in(
    conn: sqlite3.Connection, tree: str
) -> tuple[tuple[int, int, str, str], ...]:
    """Every stored brief in ``tree`` that is not a brief.

    (node id, level, why, text), top level first. A pinned brief is a
    person's and is left out: its words are not a model's reply.
    """
    held = pins.pinned(conn, pins.BRIEF)
    rows = conn.execute(
        "SELECT b.node_id AS id, b.node_id AS node_id, n.level AS level, "
        "b.flagged AS flagged, "
        f"b.text AS text, {TEMPLATE} AS template FROM briefs b "
        "JOIN nodes n ON n.id = b.node_id "
        "WHERE n.tree = ? ORDER BY n.level DESC, b.node_id",
        (tree,),
    ).fetchall()
    return tuple(
        (int(row["id"]), int(row["level"]), why, str(row["text"]))
        for row in rows
        if int(row["id"]) not in held and (why := unusable(conn, row))
    )


def stale_or_missing(
    conn: sqlite3.Connection,
    tree: str,
    level: int,
    prompt_hash: str,
    model_name: str,
    model_fingerprint: str | None = None,
    only: int | None = None,
) -> tuple[int, ...]:
    """Return ids of nodes at (tree, level) needing a (re)brief.

    ``only`` narrows the pass to one topic: a person fixing one stale brief
    must not pay for every other topic that happens to be stale too.

    A node needs work when it has no brief, or when its brief is stale — its
    member set changed, or the resolved prompt template hash / model no longer
    match the provenance it was written with.

    A node whose brief is PINNED needs no work whatever its signature says:
    the text is the operator's, and re-briefing it is the silent
    revert the pin exists to prevent. Held back here, at selection, so no
    caller can forget — and so the LLM call is never made in the first place.
    """
    node_ids = [
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ? AND level = ? "
            "AND (? IS NULL OR id = ?) ORDER BY id",
            (tree, level, only, only),
        ).fetchall()
    ]
    held = pins.pinned(conn, pins.BRIEF)
    result: list[int] = []
    for node_id in node_ids:
        if node_id in held:
            continue
        row = get(conn, node_id)
        if row is None or not _is_fresh(
            conn,
            row,
            member_signature(conn, node_id),
            prompt_hash,
            model_name,
            model_fingerprint,
        ):
            result.append(node_id)
    return tuple(result)


def scoped_node(scope: dict[str, object]) -> int | None:
    """The one topic a job's scope names, if it names one."""
    node = scope.get("node")
    return (
        node if isinstance(node, int) and not isinstance(node, bool) else None
    )


def stale_why(conn: sqlite3.Connection, node_id: int) -> str:
    """Why a topic's brief is listed as unusable, in a person's words.

    Meant for a topic `triage.unanswerable` lists: "" only for a pinned brief.
    The prompt and the model are not resolved here, so a listed brief whose
    sections are unchanged and which no one marked stale is the prompt or
    the model that moved: the one cause left once the others are ruled out.
    Called on a fresh brief it would say that too, so do not.
    """
    row = get(conn, node_id)
    if row is None:
        return "it has no brief yet"
    if pins.is_pinned(conn, pins.BRIEF, node_id):
        return ""
    if row["stale"]:
        return "something beneath it changed since it was written"
    why = unusable(conn, {**dict(row), "template": _template(conn, row)})
    if why:
        return f"what was stored is not a brief ({why})"
    if row["member_signature"] != member_signature(conn, node_id):
        return "its members changed since it was written"
    return "its prompt or model changed since it was written"


def settled(conn: sqlite3.Connection, node_id: int) -> bool:
    """Whether a topic's brief is unusable yet no rewrite will change it.

    A settled echo: the next sync and a scoped rewrite both leave it
    until its members, prompt or model change, so only a person can fix it.
    The prompt and model are not resolved here (see `stale_why`): a page that
    lists the topic reads a moved one as settled until the next sync rewrites.
    """
    row = get(conn, node_id)
    if row is None or row["stale"]:
        return False
    return (
        bool(unusable(conn, row))
        and not _rewritable(conn, row)
        and row["member_signature"] == member_signature(conn, node_id)
    )


def _template(conn: sqlite3.Connection, row: sqlite3.Row) -> object:
    found = conn.execute(
        "SELECT json_extract(config, '$.template') AS t FROM registry "
        "WHERE collection = 'prompts' AND name = ?",
        (row["prompt_name"],),
    ).fetchone()
    return None if found is None else found["t"]


def counts(
    conn: sqlite3.Connection,
    tree: str,
    level: int,
    prompt_hash: str,
    model_name: str,
    model_fingerprint: str | None = None,
) -> tuple[int, int]:
    """Return (fresh, stale) over the existing briefs at (tree, level)."""
    fresh = stale = 0
    rows = conn.execute(
        "SELECT b.node_id AS id FROM briefs b JOIN nodes n ON n.id = b.node_id "
        "WHERE n.tree = ? AND n.level = ?",
        (tree, level),
    ).fetchall()
    for row in rows:
        node_id = int(row["id"])
        brief = get(conn, node_id)
        assert brief is not None
        if _is_fresh(
            conn,
            brief,
            member_signature(conn, node_id),
            prompt_hash,
            model_name,
            model_fingerprint,
        ):
            fresh += 1
        else:
            stale += 1
    return fresh, stale


def level_briefs(
    conn: sqlite3.Connection, tree: str, level: int
) -> tuple[tuple[int, str], ...]:
    """Return (node_id, brief text) for every node at (tree, level)."""
    rows = conn.execute(
        "SELECT b.node_id AS id, b.text AS text FROM briefs b "
        "JOIN nodes n ON n.id = b.node_id WHERE n.tree = ? AND n.level = ? "
        "ORDER BY b.node_id",
        (tree, level),
    ).fetchall()
    return tuple((int(row["id"]), row["text"]) for row in rows)


@dataclass(frozen=True)
class ReduceInput:
    """What a node's brief is written from, and what it may therefore cite.

    ``texts`` and ``uris`` come from the SAME rows by construction. As two
    queries, with a reference list that does not join ``condensations``, a
    member with no condensation is silently dropped from the LLM input while
    still being cited, and the brief claims provenance it does not have.
    ``dropped`` is how many members contributed nothing, which is the node's
    flag, not a silence.
    """

    texts: tuple[str, ...]
    uris: tuple[str, ...]
    dropped: int
    labels: tuple[str, ...] = ()  # each text's file path, aligned with texts

    @property
    def rendered(self) -> str:
        """The texts as the prompt receives them: grouped under their file."""
        return labeled(zip(self.labels, self.texts, strict=True))


def labeled(pairs: Iterable[tuple[str, str]]) -> str:
    """Texts under ``=== label ===`` headers, consecutive equal labels merged.

    The research prompts read their inputs this way: a model told which file
    or which group each text comes from can name it, and a file split into
    several sections reads as one file.
    """
    blocks: list[str] = []
    current = None
    for label, text in pairs:
        if label != current:
            blocks.append(f"=== {label} ===")
            current = label
        blocks.append(text)
    return "\n\n".join(blocks)


def reduce_input(
    conn: sqlite3.Connection, node_id: int, model_name: str
) -> ReduceInput:
    """A node's condensations and the URIs of exactly those condensations."""
    rows = conn.execute(
        "SELECT d.text AS text, s.uri AS uri, s.path AS path "
        "FROM node_members m "
        "JOIN sections s ON s.id = m.section_id "
        "JOIN condensations d ON d.content_hash = s.content_hash "
        "AND d.model_name = ? WHERE m.node_id = ? ORDER BY s.uri, s.id",
        (model_name, node_id),
    ).fetchall()
    members = int(
        conn.execute(
            "SELECT COUNT(*) FROM node_members WHERE node_id = ?", (node_id,)
        ).fetchone()[0]
    )
    seen: list[str] = []
    for row in rows:
        if row["uri"] not in seen:
            seen.append(row["uri"])
    return ReduceInput(
        texts=tuple(row["text"] for row in rows),
        uris=tuple(seen),
        dropped=members - len(rows),
        labels=tuple(row["path"] for row in rows),
    )


def member_condensations(
    conn: sqlite3.Connection, node_id: int, model_name: str
) -> tuple[str, ...]:
    """Return a node's member condensation texts (the reduce input)."""
    return reduce_input(conn, node_id, model_name).texts


def child_briefs(conn: sqlite3.Connection, node_id: int) -> tuple[str, ...]:
    """Return the brief texts of an upper node's child nodes (reduce input)."""
    rows = conn.execute(
        "SELECT b.text AS text FROM node_children c "
        "JOIN briefs b ON b.node_id = c.child_id WHERE c.parent_id = ? "
        "ORDER BY c.child_id",
        (node_id,),
    ).fetchall()
    return tuple(row["text"] for row in rows)


def child_inputs(
    conn: sqlite3.Connection, node_id: int
) -> tuple[tuple[str, str], ...]:
    """An upper node's child briefs, each with its title, for the prompt.

    The title is the child's own name (its stored title, else its brief's
    first line), never its id: an id in the input is copied into the output
    and means nothing to a reader.
    """
    rows = conn.execute(
        "SELECT n.title AS title, b.text AS text FROM node_children c "
        "JOIN briefs b ON b.node_id = c.child_id "
        "JOIN nodes n ON n.id = c.child_id WHERE c.parent_id = ? "
        "ORDER BY c.child_id",
        (node_id,),
    ).fetchall()
    return tuple(
        (row["title"] or _first_line(row["text"]), row["text"]) for row in rows
    )


def outside(conn: sqlite3.Connection, node_id: int) -> str:
    """The topics outside an upper node that its leaves exchange work with.

    A leaf brief written with lookups records the other topics' files it took
    a statement from (``brief_uses``), in either direction. An upper brief
    reads only its children, so a part elsewhere that re-drives this area's
    lost work, or consumes the same messages, was invisible to it: bcreg's
    filing area wrote "no part retries" a paid filing the future-effective
    job, in another area, publishes again. Each outside topic comes with its
    opening line, what passed between it and which part here, and its
    hazards.
    """
    tree = conn.execute(
        "SELECT tree FROM nodes WHERE id = ?", (node_id,)
    ).fetchone()
    if tree is None:
        return ""
    inside = set(_leaves_under(conn, node_id))
    owner: dict[str, int] = {}
    for row in conn.execute(
        "SELECT m.node_id AS node, s.source AS source, s.path AS path "
        "FROM node_members m JOIN sections s ON s.id = m.section_id "
        "JOIN nodes n ON n.id = m.node_id WHERE n.tree = ? AND n.level = 0 "
        "ORDER BY m.node_id",
        (tree["tree"],),
    ):
        owner.setdefault(f"{row['source']}/{row['path']}", int(row["node"]))
    lines: dict[int, list[str]] = {}
    for row in conn.execute(
        "SELECT node_id, file, statement FROM brief_uses ORDER BY node_id, file"
    ):
        user, other = int(row["node_id"]), owner.get(str(row["file"]))
        if other is None or (user in inside) == (other in inside):
            continue
        here, there = (user, other) if user in inside else (other, user)
        took = (
            f"{_title(conn, here)} took from it"
            if user == here
            else f"it took from {_title(conn, here)}"
        )
        lines.setdefault(there, []).append(
            f"  - {took} (`{row['file']}`): {row['statement']}"
        )
    blocks = []
    for there, taken in lines.items():
        brief = get(conn, there)
        text = brief["text"] if brief is not None else ""
        hazards = _hazards(text)
        blocks.append(
            "\n".join(
                [
                    f"- {_title(conn, there)}: {_lede(text)}".rstrip(": "),
                    *taken,
                    *([f"  Its hazards: {hazards}"] if hazards else []),
                ]
            )
        )
    return "\n".join(blocks)


def _leaves_under(conn: sqlite3.Connection, node_id: int) -> list[int]:
    found, frontier = [], [node_id]
    while frontier:
        node = frontier.pop()
        children = child_ids(conn, node)
        if children:
            frontier.extend(children)
        else:
            found.append(node)
    return found


def _title(conn: sqlite3.Connection, node_id: int) -> str:
    row = conn.execute(
        "SELECT n.title AS title, b.text AS text FROM nodes n "
        "LEFT JOIN briefs b ON b.node_id = n.id WHERE n.id = ?",
        (node_id,),
    ).fetchone()
    if row is None:
        return "untitled"
    return row["title"] or _first_line(row["text"] or "")


def _hazards(text: str) -> str:
    """A brief's Hazards section on one line, cut short.

    The opening line says what a part does, never how it fails: the bcreg
    payments area, shown business-pay's opening alone, wrote that it had no
    duplicate guard.
    """
    _, found, rest = text.partition("## Hazards")
    if not found:
        return ""
    body = rest.split("\n## ", 1)[0]
    return " ".join(body.split())[:1200]


def _lede(text: str) -> str:
    """A brief's first paragraph under its title, cut to a few lines."""
    for block in text.split("\n\n"):
        stripped = block.strip()
        if stripped and not stripped.startswith("#"):
            return " ".join(stripped.split())[:400]
    return ""


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip().strip("#*").strip()
        if stripped:
            return stripped[:120]
    return "untitled"


def child_ids(conn: sqlite3.Connection, node_id: int) -> tuple[int, ...]:
    """Return an upper node's child node ids (the mechanical references)."""
    rows = conn.execute(
        "SELECT child_id FROM node_children WHERE parent_id = ? "
        "ORDER BY child_id",
        (node_id,),
    ).fetchall()
    return tuple(int(row["child_id"]) for row in rows)


def upsert(
    conn: sqlite3.Connection,
    node_id: int,
    text: str,
    *,
    model_name: str,
    prompt_name: str,
    prompt_hash: str,
    member_signature: str,
    input_tokens: int,
    output_tokens: int,
    model_fingerprint: str | None = None,
    unfaithful: str = "[]",
    flagged: str = "",
    members: str = "[]",
    source_model: str = "",
    reason: str = "regen",
) -> None:
    """Store one node's brief with its provenance and member signature.

    A brief this replaces is first copied to ``brief_versions`` with ``reason``
    ('regen', or 'rewrite' for a hand edit), and only the newest
    ``KEEP_VERSIONS`` are kept; a first write, or one that leaves the
    text unchanged, copies nothing.

    ``unfaithful`` is the faithfulness gate's JSON verdict; default '[]'
    keeps callers that do not run the gate unchanged. ``flagged`` is the shape
    guard's reason — empty when the reply looked like a brief.
    ``members`` is the JSON list of member URIs (or child node ids) the brief
    covers: data ABOUT the brief, kept out of its text so its recall passages
    carry prose only, and re-attached by the export renderer.
    ``source_model`` is the condense model whose condensations it was written
    from, so the echo gate reads the same material later.
    """
    _keep_replaced(conn, node_id, text, reason)
    conn.execute(
        "INSERT OR REPLACE INTO briefs(node_id, text, model_name, prompt_name, "
        "prompt_hash, member_signature, input_tokens, output_tokens, "
        "model_fingerprint, unfaithful, flagged, members, source_model, "
        "created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            node_id,
            text,
            model_name,
            prompt_name,
            prompt_hash,
            member_signature,
            input_tokens,
            output_tokens,
            model_fingerprint,
            unfaithful,
            flagged,
            members,
            source_model,
            _now(),
        ),
    )


def _keep_replaced(
    conn: sqlite3.Connection, node_id: int, text: str, reason: str
) -> None:
    """Copy the stored brief aside, unless the new text is the same text."""
    stored = conn.execute(
        "SELECT text FROM briefs WHERE node_id = ?", (node_id,)
    ).fetchone()
    if stored is not None and stored["text"] == text:
        return
    conn.execute(
        "INSERT INTO brief_versions(node_id, text, model_name, written_at, "
        "replaced_at, reason, prompt_name, prompt_hash, input_tokens, "
        "output_tokens, member_signature, members, source_model, "
        "model_fingerprint, unfaithful, flagged) SELECT node_id, text, "
        "model_name, created_at, ?, ?, prompt_name, prompt_hash, input_tokens, "
        "output_tokens, member_signature, members, source_model, "
        "model_fingerprint, unfaithful, flagged "
        "FROM briefs WHERE node_id = ?",
        (_now(), reason, node_id),
    )
    conn.execute(
        "DELETE FROM brief_versions WHERE node_id = ? AND id NOT IN ("
        "SELECT id FROM brief_versions WHERE node_id = ? "
        "ORDER BY id DESC LIMIT ?)",
        (node_id, node_id, KEEP_VERSIONS),
    )


def kept_version(
    conn: sqlite3.Connection, node_id: int, text: str
) -> sqlite3.Row | None:
    """The newest kept version of a node's brief with this text, if any.

    The whole record, so a restored brief is the one that was replaced and
    not a lookalike that counts as fresh without its members.
    """
    return conn.execute(
        "SELECT model_name, prompt_name, prompt_hash, input_tokens, "
        "output_tokens, member_signature, members, source_model, "
        "model_fingerprint, unfaithful, flagged FROM brief_versions "
        "WHERE node_id = ? AND text = ? ORDER BY id DESC LIMIT 1",
        (node_id, text),
    ).fetchone()


def versions(conn: sqlite3.Connection, node_id: int) -> list[sqlite3.Row]:
    """Return a node's kept previous briefs, newest first."""
    return conn.execute(
        "SELECT text, model_name, written_at, replaced_at, reason "
        "FROM brief_versions WHERE node_id = ? ORDER BY id DESC",
        (node_id,),
    ).fetchall()


def get(conn: sqlite3.Connection, node_id: int) -> sqlite3.Row | None:
    """Return a node's brief row, or None."""
    return conn.execute(
        "SELECT node_id, text, model_name, prompt_name, prompt_hash, "
        "member_signature, input_tokens, output_tokens, model_fingerprint, "
        "unfaithful, flagged, members, stale, judged_signature, "
        f"{TEMPLATE} AS template FROM briefs b WHERE node_id = ?",
        (node_id,),
    ).fetchone()


def mark_stale(conn: sqlite3.Connection, node_id: int) -> None:
    """Flag a node's brief for regeneration without touching its members.

    A sticky-placed leaf keeps its id so its ancestor's signature is unchanged;
    propagate sets this so the next brief pass regenerates the ancestor anyway.
    """
    conn.execute("UPDATE briefs SET stale = 1 WHERE node_id = ?", (node_id,))


def mark_judged(conn: sqlite3.Connection, node_id: int, signature: str) -> None:
    """Record the member set propagate judged this brief against.

    Separate from ``member_signature`` on purpose: that one drives the
    fresh-brief skip, and a judged marker written there would suppress a genuine
    regeneration. A re-brief clears this (``upsert`` does not list the column),
    because a new brief has not been judged.
    """
    conn.execute(
        "UPDATE briefs SET judged_signature = ? WHERE node_id = ?",
        (signature, node_id),
    )


def unfaithful_count(conn: sqlite3.Connection, tree: str, level: int) -> int:
    """Return how many briefs at (tree, level) the gate flagged (for health)."""
    return int(
        conn.execute(
            "SELECT COUNT(*) FROM briefs b JOIN nodes n ON n.id = b.node_id "
            "WHERE n.tree = ? AND n.level = ? AND b.unfaithful != '[]'",
            (tree, level),
        ).fetchone()[0]
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
