"""Row storage for the jobs table: enqueue, atomic claim, status, reads.

All access is under the caller's ``Database`` lock (#008), so ``claim_next``'s
select-then-flip is atomic against other worker threads — a pending job is
claimed exactly once.
"""

from __future__ import annotations

import sqlite3

_COLUMNS = (
    "id, parent_id, tree, op, scope, status, error, error_code, "
    "error_details, result, created_at, updated_at"
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


def create_fanout(
    conn: sqlite3.Connection,
    parent_id: str,
    op: str,
    scope: str,
    leaves: list[tuple[str, str]],
    tree: str | None,
    now: str,
) -> None:
    """Insert a parent and its leaves atomically (one transaction).

    An empty fan-out records the parent ``succeeded`` with no leaves; otherwise
    the parent stays ``pending`` (the worker skips it — it has children) and
    each leaf is a runnable ``pending`` job carrying its single-item scope.
    """
    parent_status = "succeeded" if not leaves else "pending"
    with conn:
        conn.execute(
            "INSERT INTO jobs (id, parent_id, tree, op, scope, status, "
            "created_at, updated_at) VALUES (?, NULL, ?, ?, ?, ?, ?, ?)",
            (parent_id, tree, op, scope, parent_status, now, now),
        )
        conn.executemany(
            "INSERT INTO jobs (id, parent_id, tree, op, scope, status, "
            "created_at, updated_at) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)",
            [
                (leaf_id, parent_id, tree, op, leaf_scope, now, now)
                for leaf_id, leaf_scope in leaves
            ],
        )


def claim_next(conn: sqlite3.Connection, now: str) -> sqlite3.Row | None:
    """Flip the oldest runnable pending leaf to running and return it.

    A parent job (one with children) is never claimed — only leaves and
    standalone jobs run.
    """
    row = conn.execute(
        "SELECT id FROM jobs j WHERE j.status = 'pending' AND NOT EXISTS "
        "(SELECT 1 FROM jobs c WHERE c.parent_id = j.id) "
        "ORDER BY created_at, id LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    with conn:
        conn.execute(
            "UPDATE jobs SET status = 'running', updated_at = ?, heartbeat = ? "
            "WHERE id = ? AND status = 'pending'",
            (now, now, row["id"]),
        )
    return conn.execute(
        f"SELECT {_COLUMNS} FROM jobs WHERE id = ?", (row["id"],)
    ).fetchone()


def touch(conn: sqlite3.Connection, job_id: str, now: str) -> None:
    """Stamp a running job as still held by a live worker."""
    with conn:
        conn.execute(
            "UPDATE jobs SET heartbeat = ? WHERE id = ? AND status = 'running'",
            (now, job_id),
        )


def reclaim(
    conn: sqlite3.Connection, cutoff: str | None, now: str
) -> tuple[str, ...]:
    """Return running jobs with no live worker to the queue; report their ids.

    ``cutoff`` is the oldest heartbeat a live worker could have left behind;
    pass None at startup, when no worker holds anything and every running job
    is a leftover of the process that died.
    """
    where = "status = 'running'"
    params: tuple[str, ...] = ()
    if cutoff is not None:
        where += " AND (heartbeat IS NULL OR heartbeat < ?)"
        params = (cutoff,)
    rows = conn.execute(f"SELECT id FROM jobs WHERE {where}", params).fetchall()
    if not rows:
        return ()
    with conn:
        conn.executemany(
            "UPDATE jobs SET status = 'pending', heartbeat = NULL, "
            "updated_at = ? WHERE id = ? AND status = 'running'",
            [(now, row["id"]) for row in rows],
        )
    return tuple(row["id"] for row in rows)


def set_status(
    conn: sqlite3.Connection,
    job_id: str,
    status: str,
    error: str | None,
    now: str,
    result: str | None = None,
    code: str | None = None,
    details: str | None = None,
) -> None:
    """Record a job's terminal state, and what it did while it was there.

    ``result`` is the op's outcome as JSON counts (#132); None leaves the
    stored value alone, so a status flip that carries no outcome — a reclaim,
    a cancel — never erases one.
    """
    with conn:
        conn.execute(
            "UPDATE jobs SET status = ?, error = ?, error_code = ?, "
            "error_details = ?, updated_at = ?, "
            "result = COALESCE(?, result) WHERE id = ?",
            (status, error, code, details, now, result, job_id),
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
