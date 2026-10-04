"""Manual adjustments: what an operator changes by hand (M9).

Every function here does two things in one transaction — the edit, and the PIN
that keeps it (#154/#155). That coupling is the point: the spec's rule is "a
hand-edit pins the entity", not "a hand-edit and then, separately, a pin the
user must remember". The endpoints in ``server/edits`` are a thin HTTP shell
over these.

The one exception is ``release``, which is the operator explicitly handing a
node back to automation.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from hrono import notes, pins
from hrono.cluster import TooFewPoints, incubator, levels, repair, store
from hrono.cluster.recipe import MIN_POINTS
from hrono.errors import Invalid, NotFound
from hrono.recall.brief_passages import store_brief
from hrono.summarize import briefs


def node_exists(conn: sqlite3.Connection, tree: str, node_id: int) -> bool:
    row = conn.execute(
        "SELECT 1 FROM nodes WHERE id = ? AND tree = ?", (node_id, tree)
    ).fetchone()
    return row is not None


def require_node(conn: sqlite3.Connection, tree: str, node_id: int) -> None:
    """A node of ANOTHER tree is not found here, however real it is."""
    if not node_exists(conn, tree, node_id):
        raise NotFound(f"topic not found in tree {tree}: {node_id}")


def require_one_level(
    conn: sqlite3.Connection, node_ids: Sequence[int]
) -> None:
    """Refuse a merge that mixes levels; a survivor is one kind or the other.

    The survivor is the lowest id, which is deterministic and says nothing
    about which node is the right KIND: a leaf surviving a merge with its own
    grandparent would hold that branch's children under a node whose content is
    chunks (#158 G4).
    """
    seen = {_level(conn, node_id) for node_id in node_ids}
    if len(seen) > 1:
        raise Invalid(
            "a merge folds topics of ONE level: these are at levels "
            + ", ".join(str(level) for level in sorted(seen))
        )


def require_leaf(conn: sqlite3.Connection, node_id: int) -> None:
    """Refuse a topic above the leaves where sections are what moves.

    A leaf topic's content is its sections, in ``node_members``; an upper
    topic's is its children, in ``node_children``. Every operation here that
    touches members needs the first: ``merge`` and ``dissolve`` move them out
    of a node and would silently drop the children — the node retires, its
    child edges cascade away, and nothing collects an orphan above level 0
    (``attach_orphans`` reads level 0 only), so the subtree leaves the root
    and the export with no bound on how long — and ``move_section`` puts one
    IN, which above level 0 would file a chunk under a topic that is not made
    of chunks. #163 decides what surgery up there should do; until then they
    say so.
    """
    level = _level(conn, node_id)
    if level != 0:
        raise Invalid(
            f"only a leaf topic holds sections, and topic {node_id} is at "
            f"level {level}: an upper topic's content is the topics beneath "
            f"it, not sections"
        )


def require_section(conn: sqlite3.Connection, section_id: int) -> None:
    row = conn.execute(
        "SELECT 1 FROM sections WHERE id = ?", (section_id,)
    ).fetchone()
    if row is None:
        raise NotFound(f"section not found: {section_id}")


def rename(
    conn: sqlite3.Connection, tree: str, node_id: int, title: str, who: str
) -> None:
    """Name a topic, and pin its brief so the name cannot be re-derived.

    The export derives a title from the brief's first line, so leaving the
    brief free to change would hand the naming back to the model on the next
    regeneration — the silent revert in a different costume.
    """
    require_node(conn, tree, node_id)
    before = conn.execute(
        "SELECT title FROM nodes WHERE id = ?", (node_id,)
    ).fetchone()["title"]
    _set_title(conn, node_id, title)
    if before != title:
        _record(conn, node_id, "rename", who, before=before)


def _set_title(
    conn: sqlite3.Connection, node_id: int, title: str | None
) -> None:
    conn.execute("UPDATE nodes SET title = ? WHERE id = ?", (title, node_id))
    pins.pin(conn, pins.BRIEF, node_id, reason="renamed by hand")


def override_brief(
    conn: sqlite3.Connection, tree: str, node_id: int, text: str, who: str
) -> None:
    """Replace a node's brief with an operator's words, and pin it.

    Written through the same path ``brief`` writes: the node:// passages and
    their FTS rows are rebuilt, so recall answers from the operator's text
    rather than from the summary it replaced (#071/#125). Provenance records
    who wrote it — the model name is the edit itself, because a brief nobody
    can attribute is worse than one attributed to a human.
    """
    require_node(conn, tree, node_id)
    stored = briefs.get(conn, node_id)
    before = None if stored is None else str(stored["text"])
    _write_brief(conn, node_id, text, "brief written by hand")
    if before != text:
        _record(conn, node_id, "brief", who, before=before)


def _write_brief(
    conn: sqlite3.Connection,
    node_id: int,
    text: str,
    reason: str,
    author: sqlite3.Row | None = None,
) -> None:
    signature = briefs.member_signature(conn, node_id)
    by = {
        "model_name": "hand-edited",
        "prompt_name": "hand-edited",
        "prompt_hash": "",
        "input_tokens": 0,
        "output_tokens": 0,
    }
    if author is not None:
        by = {key: author[key] for key in by}
    briefs.upsert(
        conn,
        node_id,
        text,
        member_signature=signature,
        reason="rewrite",
        **by,  # type: ignore[arg-type]
    )
    store_brief(conn, node_id, text, signature)
    pins.pin(conn, pins.BRIEF, node_id, reason=reason)


def note(
    conn: sqlite3.Connection, tree: str, node_id: int, text: str, who: str
) -> int:
    """Annotate a topic; return the note's id. Notes never pin."""
    require_node(conn, tree, node_id)
    note_id = notes.add(conn, notes.NODE, node_id, text)
    _record(conn, node_id, "note", who, ref=note_id)
    return note_id


def latest_edit(conn: sqlite3.Connection, node_id: int) -> sqlite3.Row | None:
    """The topic's newest recorded edit that an undo can put back, or None.

    A rewrite of a topic that had no brief is recorded but not offered: there
    is no earlier text to restore.
    """
    row = conn.execute(
        "SELECT id, kind, before, ref, who, made_at FROM edit_log "
        "WHERE node_id = ? ORDER BY id DESC LIMIT 1",
        (node_id,),
    ).fetchone()
    if row is not None and row["kind"] == "brief" and row["before"] is None:
        return None
    return row


def undo(
    conn: sqlite3.Connection, tree: str, node_id: int, edit_id: int
) -> str:
    """Put back what the topic's latest edit replaced; return the edit's kind.

    ``edit_id`` is the edit the person was shown: if another edit has landed
    since, or this one was already undone, nothing is touched. The log is then
    cleared, so undoing twice never reaches an older edit (one step, E034).
    A restored name or brief keeps the pin an edit by hand carries.
    """
    require_node(conn, tree, node_id)
    latest = latest_edit(conn, node_id)
    if latest is None or int(latest["id"]) != edit_id:
        raise Invalid("that edit is no longer the topic's latest: reload")
    kind = str(latest["kind"])
    if kind == "rename":
        _set_title(conn, node_id, latest["before"])
    elif kind == "brief":
        before = str(latest["before"])
        _write_brief(
            conn,
            node_id,
            before,
            "brief restored by hand",
            briefs.kept_version(conn, node_id, before),
        )
    else:
        conn.execute("DELETE FROM notes WHERE id = ?", (latest["ref"],))
    conn.execute("DELETE FROM edit_log WHERE node_id = ?", (node_id,))
    return kind


def _record(
    conn: sqlite3.Connection,
    node_id: int,
    kind: str,
    who: str,
    *,
    before: str | None = None,
    ref: int | None = None,
) -> None:
    conn.execute(
        "INSERT INTO edit_log(node_id, kind, before, ref, who, made_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (node_id, kind, before, ref, who, datetime.now(UTC).isoformat()),
    )
    conn.execute(
        "DELETE FROM edit_log WHERE node_id = ? AND id < last_insert_rowid()",
        (node_id,),
    )


def release(conn: sqlite3.Connection, tree: str, node_id: int) -> int:
    """Hand a node back to automation; return how many pins were released.

    Every pin on the node, not one kind: an operator saying "hand this back"
    means the topic, not a vocabulary they have never been shown. Its undo
    goes too: a restored name or brief would pin the topic again over whatever
    the pipeline has written since (E036).
    """
    require_node(conn, tree, node_id)
    conn.execute("DELETE FROM edit_log WHERE node_id = ?", (node_id,))
    return pins.unpin_all(conn, node_id)


def reparent(
    conn: sqlite3.Connection, tree: str, node_id: int, parent_id: int
) -> None:
    """Hang a node under a chosen parent, and pin it there.

    Without the pin the next `repair` run re-attaches it by proximity, which
    is the machine disagreeing with a human and winning quietly (#155).
    """
    require_node(conn, tree, node_id)
    require_node(conn, tree, parent_id)
    if node_id == parent_id:
        raise Invalid("a topic cannot be its own parent")
    if parent_id in _descendants(conn, node_id):
        # a cycle here does not fail loudly: it detaches a whole subtree from
        # the root, and the export simply stops mentioning it.
        raise Invalid("that parent is below this topic")
    own, above = _level(conn, node_id), _level(conn, parent_id)
    if above != own + 1:
        raise Invalid(
            f"a parent sits exactly one level up: topic {node_id} is at level "
            f"{own}, so its parent must be at level {own + 1}, and topic "
            f"{parent_id} is at level {above}"
        )
    store.move_child(conn, node_id, parent_id, similarity=None)
    pins.pin(
        conn,
        pins.PARENTING,
        node_id,
        reason="reparented by hand",
        anchor=parent_id,
    )


def merge(conn: sqlite3.Connection, tree: str, node_ids: Sequence[int]) -> int:
    """Fold several topics into one; return the surviving node's id.

    The survivor is the LOWEST id, so the result does not depend on the order
    an operator happened to list them. Its membership is pinned — the operator
    decided these belong together — but its BRIEF is not: a merged topic needs
    a new summary and the next run should write one.
    """
    if len(set(node_ids)) < 2:
        raise Invalid("a merge needs at least two distinct topics")
    for node_id in node_ids:
        require_node(conn, tree, node_id)
    require_one_level(conn, node_ids)
    survivor, *rest = sorted(set(node_ids))
    for node_id in rest:
        for section_id, _hash, _path in store.node_member_rows(conn, node_id):
            store.remove_member(conn, node_id, section_id)
            store.add_member(
                conn, survivor, section_id, forced=False, similarity=None
            )
        # an upper topic's content is its CHILDREN, and they have to come too:
        # the loser's child edges cascade away with it, and a subtree detached
        # up here left the root and the export with nothing to say about it
        # (#163).
        for child_id in _children(conn, node_id):
            store.move_child(conn, child_id, survivor, similarity=None)
        store.delete_node(conn, node_id)  # its brief and passages cascade
    for section_id, _hash, _path in store.node_member_rows(conn, survivor):
        pins.pin(
            conn,
            pins.MEMBERSHIP,
            section_id,
            reason="merged by hand",
            anchor=survivor,
        )
    for child_id in _children(conn, survivor):
        pins.pin(
            conn,
            pins.PARENTING,
            child_id,
            reason="merged by hand",
            anchor=survivor,
        )
    return survivor


def dissolve(
    conn: sqlite3.Connection, tree: str, node_id: int, model_name: str
) -> dict[str, int]:
    """Retire a topic; its members re-enter the placement rule (#085).

    Through ``repair.retire`` and NOT ``repair.dissolve``: the latter carries
    the automatic repair's below-two rule, so a topic of any real size was left
    standing while the operator was told it had been dissolved, with their
    membership pins released on the way past.

    Nothing is pinned: the operator asked for these chunks to be re-placed, not
    fixed somewhere else.
    """
    require_node(conn, tree, node_id)
    if _level(conn, node_id) != 0:
        return _dissolve_upper(conn, tree, node_id, model_name)
    for section_id, _hash, _path in store.node_member_rows(conn, node_id):
        pins.unpin(conn, pins.MEMBERSHIP, section_id)
    return repair.retire(conn, tree, node_id, model_name, _batch(conn, tree))


def _dissolve_upper(
    conn: sqlite3.Connection, tree: str, node_id: int, model_name: str
) -> dict[str, int]:
    """Retire an upper topic; its CHILDREN re-enter the attach rule (#163).

    Refused when nothing is left at its level to receive them: a node with no
    siblings IS the level, and retiring it would leave every child of it
    hanging from nothing — which is the harm this ticket exists to close, not
    a thing to do on request.
    """
    if not levels.has_siblings(conn, tree, node_id):
        raise Invalid(
            f"topic {node_id} is the only topic at its level, so its children "
            f"have nowhere to go: dissolving it would detach them from the "
            f"root"
        )
    for child_id in _children(conn, node_id):
        pins.unpin(conn, pins.PARENTING, child_id)
    moved = levels.replace_children(conn, tree, node_id, model_name)
    store.delete_node(conn, node_id)
    return {"joined": len(moved), "parked": 0, "skipped": 0}


@dataclass(frozen=True)
class Move:
    """What a hand-move did, and what it left behind (#165).

    ``emptied`` is the old topic having no members left. The pipeline retires
    an empty topic on its next `repair` run and #125's trigger takes its
    summary with it, so the stale brief answers recall for at most one cycle —
    but the operator who emptied it is the one holding the context, and they
    only get to act on it if anyone tells them.
    """

    from_node: int | None
    emptied: bool


def move_section(
    conn: sqlite3.Connection, tree: str, section_id: int, node_id: int
) -> Move:
    """File a chunk under the topic an operator can see it belongs to.

    Returns what it did: the node it left (None when the chunk came from the
    PENDING POOL) and whether that node is now empty. A
    parked chunk is the case an operator most needs this for (#164): a chunk
    in the wrong topic is at least on the map, and one the placement rule
    declined is invisible until the incubator's own rules reach it. Joining
    unparks, exactly as ``assign_or_park`` does and for its reason — a chunk
    left clustered AND pending is the state that function exists to prevent.

    The new membership is recorded UNFORCED and with
    no similarity: it was placed by a human, not by proximity, and inventing a
    score would feed the misfit rate a number nobody measured — the monitor
    would then act on it, which is the machine deciding from a figure the
    machine made up.

    Pinned, or the misfit monitor migrates it back inside one batch and the
    operator watches their own correction undone (#155).
    """
    require_node(conn, tree, node_id)
    require_leaf(conn, node_id)
    current = _member_node(conn, tree, section_id)
    if current is None and not _is_parked(conn, tree, section_id):
        raise NotFound(
            f"tree {tree} holds no section {section_id}: it is in no topic "
            f"here and not in the pending pool"
        )
    if current is not None:
        store.remove_member(conn, current, section_id)
    store.add_member(conn, node_id, section_id, forced=False, similarity=None)
    incubator.unpark(conn, tree, section_id)
    pins.pin(
        conn,
        pins.MEMBERSHIP,
        section_id,
        reason="moved by hand",
        anchor=node_id,
    )
    emptied = current is not None and not store.node_member_rows(conn, current)
    return Move(from_node=current, emptied=emptied)


def _is_parked(conn: sqlite3.Connection, tree: str, section_id: int) -> bool:
    """Whether the pending pool is holding this chunk for this tree."""
    return incubator.parked_batch(conn, tree, section_id) is not None


def _member_node(
    conn: sqlite3.Connection, tree: str, section_id: int
) -> int | None:
    """The node of THIS tree holding the section, if any holds it."""
    row = conn.execute(
        "SELECT m.node_id AS id FROM node_members m JOIN nodes n "
        "ON n.id = m.node_id WHERE m.section_id = ? AND n.tree = ?",
        (section_id, tree),
    ).fetchone()
    return None if row is None else int(row["id"])


def _children(conn: sqlite3.Connection, node_id: int) -> tuple[int, ...]:
    return tuple(
        int(row["child_id"])
        for row in conn.execute(
            "SELECT child_id FROM node_children WHERE parent_id = ? "
            "ORDER BY child_id",
            (node_id,),
        ).fetchall()
    )


def _level(conn: sqlite3.Connection, node_id: int) -> int:
    """The node's level; callers have already proved it exists."""
    row = conn.execute(
        "SELECT level FROM nodes WHERE id = ?", (node_id,)
    ).fetchone()
    return int(row["level"])


def _descendants(conn: sqlite3.Connection, node_id: int) -> set[int]:
    """Every node below ``node_id``, so a reparent cannot form a cycle."""
    seen: set[int] = set()
    frontier = [node_id]
    while frontier:
        current = frontier.pop()
        for row in conn.execute(
            "SELECT child_id FROM node_children WHERE parent_id = ?",
            (current,),
        ).fetchall():
            child = int(row["child_id"])
            if child not in seen:
                seen.add(child)
                frontier.append(child)
    return seen


def _batch(conn: sqlite3.Connection, tree: str) -> int:
    row = conn.execute(
        "SELECT batch FROM tree_batch WHERE tree = ?", (tree,)
    ).fetchone()
    return int(row["batch"]) if row is not None else 0


def split(
    conn: sqlite3.Connection, tree: str, node_id: int, model_name: str
) -> tuple[int, ...]:
    """Divide a topic through the same mini-pipeline the repair uses.

    The children are NOT pinned: the operator asked for a division, and where
    each member lands inside it is still the pipeline's judgement — which is
    what they were asking it to redo.
    """
    require_node(conn, tree, node_id)
    try:
        children = repair.split(conn, tree, node_id, model_name, over=0)
    except TooFewPoints as exc:
        # the ladder's floor, not a budget: below it there is no honest
        # reduction to run, so there is nothing to divide BY (#094).
        raise Invalid(
            f"too few members to divide this topic: the grouping recipe "
            f"needs at least {MIN_POINTS}"
        ) from exc
    if not children:
        raise Invalid(
            "this topic does not divide: its members form a single dense "
            "group, so a split would invent a boundary that is not there"
        )
    return children
