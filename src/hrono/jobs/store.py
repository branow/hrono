"""Row storage for the jobs table: enqueue, atomic claim, status, reads.

All access is under the caller's ``Database`` lock (#008), so ``claim_next``'s
select-then-flip is atomic against other worker threads — a pending job is
claimed exactly once.
"""

from __future__ import annotations

import sqlite3

_COLUMNS = (
    "id, parent_id, tree, op, scope, status, error, created_at, updated_at"
)


def insert(
    conn: sqlite3.Connection,
    job_id: str,
    parent_id: str | None,
    tree: str | None,
    op: str,
    scope: str,
    now: str,
) -> None:
    with conn:
        conn.execute(
            "INSERT INTO jobs "
            "(id, parent_id, tree, op, scope, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            (job_id, parent_id, tree, op, scope, now, now),
        )


def claim_next(conn: sqlite3.Connection, now: str) -> sqlite3.Row | None:
    """Flip the oldest pending job to running and return it, or None."""
    row = conn.execute(
        "SELECT id FROM jobs WHERE status = 'pending' "
        "ORDER BY created_at, id LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    with conn:
        conn.execute(
            "UPDATE jobs SET status = 'running', updated_at = ? "
            "WHERE id = ? AND status = 'pending'",
            (now, row["id"]),
        )
    return conn.execute(
        f"SELECT {_COLUMNS} FROM jobs WHERE id = ?", (row["id"],)
    ).fetchone()


def set_status(
    conn: sqlite3.Connection,
    job_id: str,
    status: str,
    error: str | None,
    now: str,
) -> None:
    with conn:
        conn.execute(
            "UPDATE jobs SET status = ?, error = ?, updated_at = ? "
            "WHERE id = ?",
            (status, error, now, job_id),
        )


def get(conn: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
    return conn.execute(
        f"SELECT {_COLUMNS} FROM jobs WHERE id = ?", (job_id,)
    ).fetchone()


def list_jobs(
    conn: sqlite3.Connection,
    op: str | None = None,
    status: str | None = None,
) -> tuple[sqlite3.Row, ...]:
    clauses = []
    params: list[str] = []
    if op is not None:
        clauses.append("op = ?")
        params.append(op)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT {_COLUMNS} FROM jobs{where} ORDER BY created_at, id", params
    ).fetchall()
    return tuple(rows)
