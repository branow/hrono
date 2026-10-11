"""The stored health report: worked out when a tree changes, read when shown.

Working out what needs attention reads every topic's members and vectors, about
two seconds on a 9,000-section tree, so the pages never do it. The jobs that
change a tree (sync, maintain, settle) refresh the report as their last step,
the ``health`` op refreshes it on request, and the Health and home pages read
the stored copy.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from hrono.db.database import Database
from hrono.embed.model import resolve_embedding_model
from hrono.errors import AppError, DomainError
from hrono.health import attention, triage
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext


@dataclass(frozen=True)
class Report:
    """One tree's health at ``checked_at``."""

    checked_at: str
    items: tuple[triage.Item, ...]
    parked_total: int
    parked: tuple[attention.Section, ...]
    misfit_total: int
    misfits: tuple[attention.Section, ...]
    stale: tuple[attention.Stale, ...]
    held: tuple[attention.Held, ...]
    topics: tuple[tuple[int, str], ...]


def build(conn: sqlite3.Connection, tree: str) -> Report:
    """Work the report out now."""
    model = _model(conn)
    centres = attention.Centres(conn, tree, model)
    parked_total, parked = attention.waiting(conn, tree, model, centres)
    misfit_total, misfits = attention.misfits(conn, tree, model, centres)
    return Report(
        checked_at=datetime.now(UTC).isoformat(timespec="seconds"),
        items=tuple(triage.survey(conn, tree)),
        parked_total=parked_total,
        parked=tuple(parked),
        misfit_total=misfit_total,
        misfits=tuple(misfits),
        stale=tuple(attention.stale(conn, tree)),
        held=tuple(attention.held(conn, tree)),
        topics=tuple(attention.topics(conn, tree)),
    )


def save(conn: sqlite3.Connection, tree: str, report: Report) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO tree_health (tree, checked_at, report) "
        "VALUES (?, ?, ?)",
        (tree, report.checked_at, json.dumps(asdict(report))),
    )


def load(conn: sqlite3.Connection, tree: str) -> Report | None:
    """The tree's stored report, or None when it has never been checked."""
    row = conn.execute(
        "SELECT report FROM tree_health WHERE tree = ?", (tree,)
    ).fetchone()
    if row is None:
        return None
    data = json.loads(row["report"])
    return Report(
        checked_at=data["checked_at"],
        items=tuple(triage.Item(**item) for item in data["items"]),
        parked_total=data["parked_total"],
        parked=tuple(attention.Section(**s) for s in data["parked"]),
        misfit_total=data["misfit_total"],
        misfits=tuple(attention.Section(**s) for s in data["misfits"]),
        stale=tuple(attention.Stale(**s) for s in data["stale"]),
        held=tuple(attention.Held(**h) for h in data["held"]),
        topics=tuple((int(i), str(n)) for i, n in data["topics"]),
    )


def refresh(database: Database, tree: str) -> Mapping[str, int]:
    """Work the report out and store it; what it found, counted."""
    with database.connect() as conn:
        report = build(conn, tree)
    with database.write() as conn:
        save(conn, tree, report)
    return {
        "waiting": report.parked_total,
        "misfits": report.misfit_total,
        "stale": len(report.stale),
    }


def check(job: Job, context: JobContext) -> Mapping[str, int]:
    """The ``health`` op: refresh one tree's report on request."""
    return refresh(context.database, str(job.tree))


def _model(conn: sqlite3.Connection) -> str | None:
    try:
        return str(resolve_embedding_model(conn, {})["name"])
    except (AppError, DomainError):
        return None


OPS["health"] = check
