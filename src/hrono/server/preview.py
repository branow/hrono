"""What the settings page shows of a prompt preview.

The preview itself is the `brief-preview` job (`summarize/brief_preview.py`).
This is the page's two reads of it: which topics may be previewed on, and one
job read back as the panel that sets the new brief beside the current one.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from hrono import naming
from hrono.jobs import store as job_store
from hrono.jobs.model import to_job
from hrono.server import failures
from hrono.summarize import briefs
from hrono.summarize.brief_preview import ROLES

OP = "brief-preview"


@dataclass(frozen=True)
class Topic:
    """One topic a preview may run on, with the level it sits at."""

    id: int
    name: str
    level: int


@dataclass(frozen=True)
class Typed:
    """What was typed into the form when the preview was started."""

    name: str
    role: str
    template: str


@dataclass(frozen=True)
class Panel:
    """One preview run as the page shows it."""

    job: str
    live: bool
    canceled: bool
    failed: bool
    failure: failures.Failure | None
    topic: str
    tree: str
    node: int | None
    current: str | None
    text: str
    flagged: str
    tokens: str
    typed: Typed


def topics(conn: sqlite3.Connection, tree: str) -> tuple[Topic, ...]:
    """The topics of ``tree`` that hold a brief, lowest level first."""
    rows = conn.execute(
        "SELECT n.id AS id, n.level AS level FROM nodes n "
        "JOIN briefs b ON b.node_id = n.id "
        "WHERE n.tree = ? ORDER BY n.level, n.id",
        (tree,),
    ).fetchall()
    named = naming.names(conn, [int(row["id"]) for row in rows])
    return tuple(
        Topic(int(row["id"]), named[int(row["id"])], int(row["level"]))
        for row in rows
    )


def previewable(role: str) -> bool:
    """Only a role that writes a brief has one to set the new text beside."""
    return role in ROLES


def panel(conn: sqlite3.Connection, job_id: str) -> Panel | None:
    """One preview run as the page shows it, or None when it is not one."""
    row = job_store.get(conn, job_id)
    if row is None or row["op"] != OP:
        return None
    job = to_job(row)
    node = briefs.scoped_node(job.scope)
    current = None if node is None else briefs.get(conn, node)
    result = job.result or {}
    tokens = result.get("tokens")
    failed = job.status == "failed"
    return Panel(
        job=job.id,
        live=job.status in {"pending", "running"},
        canceled=job.status == "canceled",
        failed=failed,
        failure=failures.explain(job.error_code, job.error, job.error_details)
        if failed
        else None,
        topic="" if node is None else naming.name(conn, node),
        tree=job.tree,
        node=node,
        current=None if current is None else str(current["text"]),
        text=str(result.get("text") or ""),
        flagged=str(result.get("flagged") or ""),
        tokens=(
            f"{int(tokens.get('input', 0)):,} in, "
            f"{int(tokens.get('output', 0)):,} out"
            if isinstance(tokens, dict)
            else ""
        ),
        typed=Typed(
            name=str(job.scope.get("prompt") or ""),
            role=str(job.scope.get("role") or ""),
            template=str(job.scope.get("template") or ""),
        ),
    )
