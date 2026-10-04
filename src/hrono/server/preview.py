"""What the settings page shows of a prompt preview (#431).

The preview itself is the `brief-preview` job (`summarize/brief_preview.py`).
This is the page's two reads of it: which topics may be previewed on, and one
job read back as the panel that sets the new brief beside the current one.
"""

from __future__ import annotations

import sqlite3

from hrono import naming
from hrono.jobs import store as job_store
from hrono.jobs.model import to_job
from hrono.server import failures
from hrono.summarize import briefs
from hrono.summarize.brief_preview import ROLES

OP = "brief-preview"


def topics(conn: sqlite3.Connection, tree: str) -> list[dict[str, object]]:
    """The topics of ``tree`` that hold a brief, each with its display name."""
    rows = conn.execute(
        "SELECT n.id AS id FROM nodes n JOIN briefs b ON b.node_id = n.id "
        "WHERE n.tree = ? ORDER BY n.level, n.id",
        (tree,),
    ).fetchall()
    named = naming.names(conn, [int(row["id"]) for row in rows])
    return [
        {"id": int(row["id"]), "name": named[int(row["id"])]} for row in rows
    ]


def previewable(role: str) -> bool:
    """Only a role that writes a brief has one to set the new text beside."""
    return role in ROLES


def panel(conn: sqlite3.Connection, job_id: str) -> dict[str, object] | None:
    """One preview run as the page shows it, or None when it is not one."""
    row = job_store.get(conn, job_id)
    if row is None or row["op"] != OP:
        return None
    job = to_job(row)
    node = briefs.scoped_node(job.scope)
    current = None if node is None else briefs.get(conn, node)
    result = job.result or {}
    tokens = result.get("tokens")
    failed = job.status in {"failed", "canceled"}
    return {
        "job": job.id,
        "live": job.status in {"pending", "running"},
        "failed": failed,
        "failure": failures.explain(
            job.error_code, job.error, job.error_details
        )
        if failed
        else None,
        "topic": "" if node is None else naming.name(conn, node),
        "tree": job.tree,
        "node": node,
        "current": None if current is None else str(current["text"]),
        "text": str(result.get("text") or ""),
        "flagged": str(result.get("flagged") or ""),
        "tokens": (
            f"{int(tokens.get('input', 0)):,} in, "
            f"{int(tokens.get('output', 0)):,} out"
            if isinstance(tokens, dict)
            else ""
        ),
        "typed": {
            "name": str(job.scope.get("prompt") or ""),
            "role": str(job.scope.get("role") or ""),
            "template": str(job.scope.get("template") or ""),
        },
    }
