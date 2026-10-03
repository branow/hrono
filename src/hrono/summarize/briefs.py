"""Persist and read back node briefs, and gather the inputs a brief reduces.

A brief is one row per node carrying the summary text (member reference URIs
already baked in by the op), the provenance the cost API reads back (model,
prompt name + template hash, token usage), the member-set signature it was
written against, and its timestamp. ``stale_or_missing`` drives incremental
regeneration: a node needs a brief when it has none, or when its members or its
prompt/model have changed since the brief was written (T23.2). The gather
helpers join node membership to the sections' condensations (the LLM input) and
to the section URIs (the mechanical references).
"""

from __future__ import annotations

import hashlib
import sqlite3
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
    content (#068) — this is what lets #064's brief skip actually fire through a
    rebuild. Upper members sign over their child node ids (stable once the level
    below is). Tokens are prefixed so a content hash and node id never collide.
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

    The fingerprint (#191) is what the model NAME could not say: repointing
    `sonnet` at another upstream model leaves the name identical and every
    word different. A brief written before the column existed carries NULL,
    and NULL is not staleness — see `0034_brief_model_fingerprint.sql`.

    A brief that was written, retried and stored flagged is not re-paid while
    nothing it was written from changes (E019): the member signature, prompt
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
    model will echo again (E019). A talk-back (#217) is retried, and so is a
    flag the gate would no longer raise.
    """
    if not unusable(conn, row):
        return False
    return not (
        row["flagged"] == shape.ECHOES
        and refusal(conn, row["node_id"], "", row["text"], row["template"])
        == shape.ECHOES
    )


# The template of the prompt a brief was written with, as a column: a query
# over ``briefs b`` selects ``{TEMPLATE} AS template`` and hands it to
# ``refusal``, which cannot tell an echo of the prompt without it (E015).
TEMPLATE = (
    "(SELECT json_extract(p.config, '$.template') FROM registry p "
    "WHERE p.collection = 'prompts' AND p.name = b.prompt_name)"
)


def unusable(conn: sqlite3.Connection, row: sqlite3.Row) -> str:
    """Why a stored brief is not a brief, or "" when it is one (#217).

    The flag stored when it was written, or the CURRENT gate's verdict on its
    text — so a brief stored before a rule existed is caught by it too, and
    one that is not a brief is never fresh: the next brief pass rewrites it,
    and only it. A settled ``echoes-the-prompt`` is the exception: it is listed
    but stays until its members, prompt or model change (E019).
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
    it (E019): that is rare, and a page of nodes must not read the corpus.
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
    prompt (E019).

    Exactly the reduce input ``brief`` gates against: a condensation a
    previous condense model left in the cache is not part of it, or a settled
    echo would read as a different one and be re-paid.
    """
    source = _source_model(conn, node_id)
    texts = member_condensations(conn, node_id, source) or child_briefs(
        conn, node_id
    )
    return "\n\n".join(texts)


def _source_model(conn: sqlite3.Connection, node_id: int) -> str:
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
    """Every stored brief in ``tree`` that is not a brief (#217).

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
) -> tuple[int, ...]:
    """Return ids of nodes at (tree, level) needing a (re)brief.

    A node needs work when it has no brief, or when its brief is stale — its
    member set changed, or the resolved prompt template hash / model no longer
    match the provenance it was written with.

    A node whose brief is PINNED needs no work whatever its signature says
    (#154): the text is the operator's, and re-briefing it is the silent
    revert the pin exists to prevent. Held back here, at selection, so no
    caller can forget — and so the LLM call is never made in the first place.
    """
    node_ids = [
        int(row["id"])
        for row in conn.execute(
            "SELECT id FROM nodes WHERE tree = ? AND level = ? ORDER BY id",
            (tree, level),
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

    ``texts`` and ``uris`` come from the SAME rows by construction (#122). They
    used to be two queries and the reference list did not join ``condensations``
    — so a member with no condensation was silently dropped from the LLM input
    while still being cited, and the brief claimed provenance it did not have.
    ``dropped`` is how many members contributed nothing, which is the node's
    flag, not a silence.
    """

    texts: tuple[str, ...]
    uris: tuple[str, ...]
    dropped: int


def reduce_input(
    conn: sqlite3.Connection, node_id: int, model_name: str
) -> ReduceInput:
    """A node's condensations and the URIs of exactly those condensations."""
    rows = conn.execute(
        "SELECT d.text AS text, s.uri AS uri FROM node_members m "
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
) -> None:
    """Store one node's brief with its provenance and member signature.

    ``unfaithful`` is the faithfulness gate's JSON verdict (#063); default '[]'
    keeps callers that do not run the gate unchanged. ``flagged`` is the shape
    guard's reason (#103) — empty when the reply looked like a brief.
    ``members`` is the JSON list of member URIs (or child node ids) the brief
    covers: data ABOUT the brief, kept out of its text so #071's passages carry
    prose only (#102), and re-attached by the export renderer.
    ``source_model`` is the condense model whose condensations it was written
    from, so the echo gate reads the same material later (E019).
    """
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
    """Flag a node's brief for regeneration without touching its members (#087).

    A sticky-placed leaf keeps its id so #068's ancestor signature is unchanged;
    propagate sets this so the next brief pass regenerates the ancestor anyway.
    """
    conn.execute("UPDATE briefs SET stale = 1 WHERE node_id = ?", (node_id,))


def mark_judged(conn: sqlite3.Connection, node_id: int, signature: str) -> None:
    """Record the member set propagate judged this brief against (#110).

    Separate from ``member_signature`` on purpose: that one drives #064's
    re-brief skip, and a judged marker written there would suppress a genuine
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
