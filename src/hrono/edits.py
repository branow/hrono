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

from hrono import pins
from hrono.cluster import TooFewPoints, incubator, repair, store
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
        raise NotFound(f"node not found in tree {tree}: {node_id}")


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
            f"only a leaf topic holds sections, and node {node_id} is at "
            f"level {level}: an upper topic's content is the topics beneath "
            f"it, not chunks"
        )


def require_section(conn: sqlite3.Connection, section_id: int) -> None:
    row = conn.execute(
        "SELECT 1 FROM sections WHERE id = ?", (section_id,)
    ).fetchone()
    if row is None:
        raise NotFound(f"section not found: {section_id}")


def rename(
    conn: sqlite3.Connection, tree: str, node_id: int, title: str
) -> None:
    """Name a topic, and pin its brief so the name cannot be re-derived.

    The export derives a title from the brief's first line, so leaving the
    brief free to change would hand the naming back to the model on the next
    regeneration — the silent revert in a different costume.
    """
    require_node(conn, tree, node_id)
    conn.execute("UPDATE nodes SET title = ? WHERE id = ?", (title, node_id))
    pins.pin(conn, pins.BRIEF, node_id, reason="renamed by hand")


def override_brief(
    conn: sqlite3.Connection, tree: str, node_id: int, text: str
) -> None:
    """Replace a node's brief with an operator's words, and pin it.

    Written through the same path ``brief`` writes: the node:// passages and
    their FTS rows are rebuilt, so recall answers from the operator's text
    rather than from the summary it replaced (#071/#125). Provenance records
    who wrote it — the model name is the edit itself, because a brief nobody
    can attribute is worse than one attributed to a human.
    """
    require_node(conn, tree, node_id)
    signature = briefs.member_signature(conn, node_id)
    briefs.upsert(
        conn,
        node_id,
        text,
        model_name="hand-edited",
        prompt_name="hand-edited",
        prompt_hash="",
        member_signature=signature,
        input_tokens=0,
        output_tokens=0,
    )
    store_brief(conn, node_id, text, signature)
    pins.pin(conn, pins.BRIEF, node_id, reason="brief written by hand")


def release(conn: sqlite3.Connection, tree: str, node_id: int) -> int:
    """Hand a node back to automation; return how many pins were released.

    Every pin on the node, not one kind: an operator saying "hand this back"
    means the topic, not a vocabulary they have never been shown.
    """
    require_node(conn, tree, node_id)
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
        raise Invalid("a node cannot be its own parent")
    if parent_id in _descendants(conn, node_id):
        # a cycle here does not fail loudly: it detaches a whole subtree from
        # the root, and the export simply stops mentioning it.
        raise Invalid("that parent is below this node")
    own, above = _level(conn, node_id), _level(conn, parent_id)
    if above != own + 1:
        raise Invalid(
            f"a parent sits exactly one level up: node {node_id} is at level "
            f"{own}, so its parent must be at level {own + 1}, and node "
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
        raise Invalid("a merge needs at least two distinct nodes")
    for node_id in node_ids:
        require_node(conn, tree, node_id)
        require_leaf(conn, node_id)
    survivor, *rest = sorted(set(node_ids))
    for node_id in rest:
        for section_id, _hash, _path in store.node_member_rows(conn, node_id):
            store.remove_member(conn, node_id, section_id)
            store.add_member(
                conn, survivor, section_id, forced=False, similarity=None
            )
        store.delete_node(conn, node_id)  # its brief and passages cascade
    for section_id, _hash, _path in store.node_member_rows(conn, survivor):
        pins.pin(
            conn,
            pins.MEMBERSHIP,
            section_id,
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
    require_leaf(conn, node_id)
    for section_id, _hash, _path in store.node_member_rows(conn, node_id):
        pins.unpin(conn, pins.MEMBERSHIP, section_id)
    return repair.retire(conn, tree, node_id, model_name, _batch(conn, tree))


def move_section(
    conn: sqlite3.Connection, tree: str, section_id: int, node_id: int
) -> int | None:
    """File a chunk under the topic an operator can see it belongs to.

    Returns the node it left, or None when it came from the PENDING POOL. A
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
    return current


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
            f"too few members to divide this topic: the clustering recipe "
            f"needs at least {MIN_POINTS}"
        ) from exc
    if not children:
        raise Invalid(
            "this topic does not divide: its members form a single dense "
            "group, so a split would invent a boundary that is not there"
        )
    return children
