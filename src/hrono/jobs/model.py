"""Jobs domain: the leaf statuses, the Job record, and scope (de)serialization.

Every slow operation runs as a job. This is storage-facing only — the worker
that executes jobs and the ops themselves land later. The parent-only
``partial`` status is derived at read time (T57), never stored, so it is absent
from ``JobStatus`` here.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from enum import StrEnum


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass(frozen=True)
class Job:
    id: str
    parent_id: str | None
    tree: str | None
    op: str
    scope: dict[str, object]
    status: str
    error: str | None
    created_at: str
    updated_at: str


def serialize_scope(scope: dict[str, object]) -> str:
    """Serialize a scope selector to the text stored on the row."""
    return json.dumps(scope)


def deserialize_scope(text: str) -> dict[str, object]:
    """Parse the stored scope text back into a selector."""
    return json.loads(text)


def to_job(row: sqlite3.Row) -> Job:
    """Read a ``jobs`` row into a ``Job`` (scope parsed to a selector)."""
    return Job(
        id=row["id"],
        parent_id=row["parent_id"],
        tree=row["tree"],
        op=row["op"],
        scope=deserialize_scope(row["scope"]),
        status=row["status"],
        error=row["error"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
