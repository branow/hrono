"""Row storage for the jobs table: enqueue, atomic claim, status, reads.

All access is under the caller's ``Database`` lock, so ``claim_next``'s
select-then-flip is atomic against other worker threads — a pending job is
claimed exactly once.
"""

from __future__ import annotations

import sqlite3

from hrono.db.database import tx

_COLUMNS = (
    "id, parent_id, tree, op, scope, status, error, error_code, "
    "error_details, result, started_by, created_at, updated_at"
)


def insert(
    conn: sqlite3.Connection,
    job_id: str,
    parent_id: str | None,
    tree: str | None,
    op: str,
    scope: str,
    now: str,
    started_by: str | None = None,
) -> None:
    with tx(conn):
        conn.execute(
            "INSERT INTO jobs (id, parent_id, tree, op, scope, status, "
            "started_by, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
            (job_id, parent_id, tree, op, scope, started_by, now, now),
        )


def create_fanout(
    conn: sqlite3.Connection,
    parent_id: str,
    op: str,
    scope: str,
    leaves: list[tuple[str, str]],
    tree: str | None,
    now: str,
    started_by: str | None = None,
) -> None:
    """Insert a parent and its leaves atomically (one transaction).

    An empty fan-out records the parent ``succeeded`` with no leaves; otherwise
    the parent stays ``pending`` (the worker skips it — it has children) and
    each leaf is a runnable ``pending`` job carrying its single-item scope.
    """
    parent_status = "succeeded" if not leaves else "pending"
    with tx(conn):
        conn.execute(
            "INSERT INTO jobs (id, parent_id, tree, op, scope, status, "
            "started_by, created_at, updated_at) "
            "VALUES (?, NULL, ?, ?, ?, ?, ?, ?, ?)",
            (parent_id, tree, op, scope, parent_status, started_by, now, now),
        )
        conn.executemany(
            "INSERT INTO jobs (id, parent_id, tree, op, scope, status, "
            "started_by, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?)",
            [
                (leaf_id, parent_id, tree, op, leaf_scope, started_by, now, now)
                for leaf_id, leaf_scope in leaves
            ],
        )


_RUNNABLE = (
    "FROM jobs j WHERE j.status = 'pending' AND NOT EXISTS "
    "(SELECT 1 FROM jobs c WHERE c.parent_id = j.id)"
)


def has_runnable(conn: sqlite3.Connection) -> bool:
    """Whether anything is waiting — safe to ask under the READ door.

    The worker polls dozens of times a second, and asking through ``write()``
    took ``BEGIN IMMEDIATE`` on every poll of an idle server, making every
    HTTP writer compete with a loop that had nothing to do. The claim itself
    still happens under the write lock; this only decides whether to take it.
    """
    return conn.execute(f"SELECT 1 {_RUNNABLE} LIMIT 1").fetchone() is not None


def claim_next(conn: sqlite3.Connection, now: str) -> sqlite3.Row | None:
    """Flip the oldest runnable pending leaf to running and return it.

    A parent job (one with children) is never claimed — only leaves and
    standalone jobs run.
    """
    row = conn.execute(
        f"SELECT id {_RUNNABLE} ORDER BY created_at, id LIMIT 1"  # noqa: S608
    ).fetchone()
    if row is None:
        return None
    with tx(conn):
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
    with tx(conn):
        conn.execute(
            "UPDATE jobs SET heartbeat = ? WHERE id = ? AND status = 'running'",
            (now, job_id),
        )


MAX_ATTEMPTS = 3  # requeues a stranded job gets before it is a crash loop


def reclaim(
    conn: sqlite3.Connection, cutoff: str | None, now: str
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Requeue stranded running jobs; fail the crash loops. Both lists back.

    ``cutoff`` is the oldest heartbeat a live worker could have left behind;
    pass None at startup, when no worker holds anything and every running job
    is a leftover of the process that died.

    A job stranded ``MAX_ATTEMPTS`` times is not stranded, it is a job that
    KILLS its worker — re-queueing it forever is a crash loop nobody sees, so
    it fails with a code an operator can find instead.
    """
    where = "status = 'running'"
    params: tuple[str, ...] = ()
    if cutoff is not None:
        where += " AND (heartbeat IS NULL OR heartbeat < ?)"
        params = (cutoff,)
    rows = conn.execute(
        f"SELECT id, attempts FROM jobs WHERE {where}",  # noqa: S608
        params,
    ).fetchall()
    if not rows:
        return (), ()
    requeued = [r["id"] for r in rows if int(r["attempts"]) < MAX_ATTEMPTS]
    looping = [r["id"] for r in rows if int(r["attempts"]) >= MAX_ATTEMPTS]
    with tx(conn):
        conn.executemany(
            "UPDATE jobs SET status = 'pending', heartbeat = NULL, "
            "attempts = attempts + 1, updated_at = ? "
            "WHERE id = ? AND status = 'running'",
            [(now, job_id) for job_id in requeued],
        )
        conn.executemany(
            "UPDATE jobs SET status = 'failed', heartbeat = NULL, "
            "error = 'this job took its worker down on every try', "
            "error_code = 'crash-loop', updated_at = ? "
            "WHERE id = ? AND status = 'running'",
            [(now, job_id) for job_id in looping],
        )
    return tuple(requeued), tuple(looping)


def set_status(
    conn: sqlite3.Connection,
    job_id: str,
    status: str,
    error: str | None,
    now: str,
    result: str | None = None,
    code: str | None = None,
    details: str | None = None,
    expected: str | None = None,
) -> None:
    """Record a job's terminal state, and what it did while it was there.

    ``result`` is the op's outcome as JSON counts; None leaves the
    stored value alone, so a status flip that carries no outcome — a reclaim,
    a cancel — never erases one.

    ``expected`` guards the flip: a worker finishing a job writes only over
    ``running``, so a cancel (or a reclaim) that moved the row first is not
    overwritten by a slower thread announcing an outcome nobody wants anymore.
    """
    guard = "" if expected is None else "AND status = ? "
    with tx(conn):
        conn.execute(
            "UPDATE jobs SET status = ?, error = ?, error_code = ?, "
            "error_details = ?, updated_at = ?, "
            f"result = COALESCE(?, result) WHERE id = ? {guard}",  # noqa: S608
            (
                status,
                error,
                code,
                details,
                now,
                result,
                job_id,
                *(() if expected is None else (expected,)),
            ),
        )


def finalize_parent(conn: sqlite3.Connection, parent_id: str, now: str) -> None:
    """Write a fan-out parent's terminal status once its last child ends.

    Parents were inserted 'pending' and derived their status on read — so
    every finished run's parent stayed in the 'pending' set that the claim
    scan walks on every poll and that ``?status=pending`` returns, forever.
    The derived rule is ``aggregate.rollup``'s; this writes it down exactly
    when it stops being able to change.
    """
    with tx(conn):
        conn.execute(
            "UPDATE jobs SET status = ("
            "    SELECT CASE"
            "        WHEN SUM(c.status = 'failed') > 0 THEN 'failed'"
            "        WHEN SUM(c.status = 'canceled') > 0 THEN 'canceled'"
            "        ELSE 'succeeded'"
            "    END FROM jobs c WHERE c.parent_id = jobs.id"
            "), updated_at = ? "
            "WHERE id = ? AND status = 'pending'"
            "  AND EXISTS (SELECT 1 FROM jobs c WHERE c.parent_id = jobs.id)"
            "  AND NOT EXISTS ("
            "      SELECT 1 FROM jobs c WHERE c.parent_id = jobs.id"
            "        AND c.status IN ('pending', 'running'))",
            (now, parent_id),
        )


JOB_RETENTION_DAYS = 30  # terminal runs older than this are swept


def prune(conn: sqlite3.Connection, cutoff: str) -> int:
    """Delete terminal runs not touched since ``cutoff``; return rows removed.

    Nothing ever deleted a job row, so the table — and with it the claim
    scan's 'pending' set, the runs CTE and ``GET /jobs`` — grew without bound.
    Children go with their root: a root is deleted only when it is terminal
    and old, and its children are deleted first so no orphan rows survive.
    """
    terminal = "('succeeded', 'failed', 'canceled')"
    with tx(conn):
        children = conn.execute(
            f"DELETE FROM jobs WHERE parent_id IN "  # noqa: S608
            f"(SELECT id FROM jobs p WHERE p.parent_id IS NULL "
            f"AND p.status IN {terminal} AND p.updated_at < ?)",
            (cutoff,),
        ).rowcount
        roots = conn.execute(
            f"DELETE FROM jobs WHERE parent_id IS NULL "  # noqa: S608
            f"AND status IN {terminal} AND updated_at < ? "
            f"AND NOT EXISTS (SELECT 1 FROM jobs c "
            f"WHERE c.parent_id = jobs.id)",
            (cutoff,),
        ).rowcount
    return int(children) + int(roots)


def get(conn: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
    return conn.execute(
        f"SELECT {_COLUMNS} FROM jobs WHERE id = ?", (job_id,)
    ).fetchone()


def children(
    conn: sqlite3.Connection, parent_id: str
) -> tuple[sqlite3.Row, ...]:
    """A parent's child jobs, oldest first."""
    return tuple(
        conn.execute(
            f"SELECT {_COLUMNS} FROM jobs WHERE parent_id = ? "  # noqa: S608
            "ORDER BY created_at, id",
            (parent_id,),
        ).fetchall()
    )


def page_roots(
    conn: sqlite3.Connection,
    tree: str,
    *,
    op: str = "",
    status: str = "",
    also: str = "",
    limit: int,
    offset: int,
) -> tuple[sqlite3.Row, ...]:
    """One page of a tree's runs, newest first, filtered and paged in SQL.

    The runs list reads one page of rows however many runs a tree has.
    ``status`` filters by the DERIVED status, the one ``aggregate.rollup``
    gives a parent from its children; ``_ROLLED`` is that rule in SQL, and a
    test holds the two to the same answers. ``also`` is a second status the
    filter accepts, for a caller whose one word covers two (`running` on the
    page covers `partial`); empty matches nothing, since no run has no status.
    """
    rows = conn.execute(
        f"{_ROLLED} SELECT {_COLUMNS} FROM rolled_jobs {_ROOTS} "
        "ORDER BY created_at DESC, id DESC LIMIT :limit OFFSET :offset",
        {
            "tree": tree,
            "op": op,
            "status": status,
            "also": also,
            "limit": limit,
            "offset": offset,
        },
    ).fetchall()
    return tuple(rows)


def count_roots(
    conn: sqlite3.Connection,
    tree: str,
    *,
    op: str = "",
    status: str = "",
    also: str = "",
) -> int:
    """How many of a tree's runs ``page_roots`` would page through."""
    row = conn.execute(
        f"{_ROLLED} SELECT COUNT(*) FROM rolled_jobs {_ROOTS}",
        {"tree": tree, "op": op, "status": status, "also": also},
    ).fetchone()
    return int(row[0])


def root_ops(conn: sqlite3.Connection, tree: str) -> tuple[str, ...]:
    """Every op a tree has run, once each, for the runs list's op filter."""
    rows = conn.execute(
        "SELECT DISTINCT op FROM jobs WHERE parent_id IS NULL "
        "AND COALESCE(tree, 'default') = ? ORDER BY op",
        (tree,),
    ).fetchall()
    return tuple(str(row["op"]) for row in rows)


_ROOTS = (
    "WHERE parent_id IS NULL AND COALESCE(tree, 'default') = :tree "
    "AND (:op = '' OR op = :op) AND (:status = '' OR rolled = :status "
    "OR rolled = :also)"
)

_ROLLED = """
WITH kids AS (
    SELECT parent_id,
           COUNT(*) AS total,
           SUM(status IN ('succeeded', 'failed', 'canceled')) AS done,
           SUM(status = 'failed') AS failed,
           SUM(status = 'canceled') AS canceled,
           SUM(status = 'succeeded') AS succeeded,
           SUM(status = 'running') AS running
    FROM jobs WHERE parent_id IS NOT NULL GROUP BY parent_id
),
rolled_jobs AS (
    SELECT jobs.*,
           CASE
               WHEN kids.total IS NULL THEN jobs.status
               WHEN kids.failed > 0 THEN 'failed'
               WHEN kids.canceled > 0 THEN 'canceled'
               WHEN kids.done = kids.total THEN 'succeeded'
               WHEN kids.succeeded > 0 THEN 'partial'
               WHEN kids.running > 0 THEN 'running'
               ELSE 'pending'
           END AS rolled
    FROM jobs LEFT JOIN kids ON kids.parent_id = jobs.id
)
"""


LIST_CAP = 500  # the most rows one listing returns


def list_jobs(
    conn: sqlite3.Connection,
    op: str | None = None,
    status: str | None = None,
    limit: int = LIST_CAP,
) -> tuple[sqlite3.Row, ...]:
    """At most ``limit`` matching jobs, NEWEST window, oldest first within it.

    Unbounded, the response grew with the table's whole history; the newest
    window is the one an operator filtering by op or status is asking about.
    """
    clauses = []
    params: list[object] = []
    if op is not None:
        clauses.append("op = ?")
        params.append(op)
    if status is not None:
        clauses.append("status = ?")
        params.append(status)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM (SELECT {_COLUMNS} FROM jobs{where} "  # noqa: S608
        "ORDER BY created_at DESC, id DESC LIMIT ?) ORDER BY created_at, id",
        (*params, min(limit, LIST_CAP)),
    ).fetchall()
    return tuple(rows)
