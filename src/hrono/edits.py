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

from hrono import pins
from hrono.errors import NotFound
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
