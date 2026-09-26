"""Jobs routes: read any job (reader+), and the admin-only service door.

``POST /jobs`` enqueues ANY registered op. It exists because the September QA
run had to insert job rows into SQLite by hand to find out why a tree was stuck
— that gap is real. It is deliberately not pretty, and deliberately has no CLI
command (#139): the lifecycle stages must run in one order, and running them out
of order leaves a map that looks right and is quietly wrong (#122, #137). A user
runs ``hrono tree sync``; an operator debugging a stuck tree reaches for curl
and should feel that they have.

ADMIN, not writer, for the same reason: this can run an expensive or destructive
stage out of sequence, and the role should say so.
"""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field

from hrono.auth.users import User
from hrono.errors import BadRequest, NotFound
from hrono.jobs import store
from hrono.jobs.aggregate import Rollup, rollup
from hrono.jobs.model import Job, to_job
from hrono.jobs.ops import OPS
from hrono.jobs.scope import fan_out, fans_out
from hrono.jobs.worker import enqueue
from hrono.server.auth import require_role

router = APIRouter()

Reader = Annotated[User, Depends(require_role("reader"))]
Admin = Annotated[User, Depends(require_role("admin"))]


class JobRequest(BaseModel):
    """One op to run, and the scope to run it over."""

    op: str
    scope: dict[str, object] = Field(default_factory=dict)
    tree: str | None = None


def _error(job: Job) -> dict[str, object] | None:
    """A failure in the SAME envelope every other surface answers in (#109)."""
    if job.error is None and job.error_code is None:
        return None
    return {
        "code": job.error_code or "internal-error",
        "message": job.error,
        "details": job.error_details,
    }


def _job(row: sqlite3.Row, rolled: Rollup | None = None) -> dict[str, object]:
    job = to_job(row)
    answer: dict[str, object] = {
        "id": job.id,
        "parent_id": job.parent_id,
        "tree": job.tree,
        "op": job.op,
        "scope": job.scope,
        "status": rolled.status if rolled is not None else job.status,
        "error": _error(job),
        "result": job.result,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }
    if rolled is not None:
        answer["progress"] = {"done": rolled.done, "total": rolled.total}
    return answer


def _rolled(conn: sqlite3.Connection, job_id: str) -> Rollup | None:
    """A parent's children as one answer; None for a leaf (T57.1).

    The parent's OWN status row is not consulted: the work is in the children,
    and a parent row that says `running` while every child has finished is the
    stale second source of truth this avoids having.
    """
    return rollup([str(row["status"]) for row in store.children(conn, job_id)])


@router.post("/jobs", status_code=status.HTTP_201_CREATED)
def run_job(body: JobRequest, request: Request, _: Admin) -> dict[str, str]:
    """Enqueue any registered op. A service door, not a product surface.

    **Stages run out of order can leave a tree that looks fine and is wrong.**
    `propagate` before `update` judges content that has not arrived; `brief`
    before `propagate` silently prevents any ancestor from ever being marked
    stale (#137). Use ``POST /trees/{name}/sync`` unless you are debugging.
    """
    if body.op not in OPS:
        raise BadRequest(
            f"unknown op: {body.op}",
            details={"registered": sorted(OPS)},
        )
    database = request.app.state.db
    if fans_out(body.op, body.scope):
        # a source-scoped op over every source is a job PER SOURCE, under one
        # parent that reports what they add up to (#172). Until #175 this
        # machinery existed and nothing called it, so every such request ran as
        # one opaque job.
        return {
            "job_id": fan_out(database, body.op, body.scope, tree=body.tree)
        }
    job_id = enqueue(database, body.op, body.scope, tree=body.tree)
    return {"job_id": job_id}


@router.get("/jobs")
def list_jobs(
    request: Request,
    _: Reader,
    op: str | None = None,
    status: str | None = None,
) -> list[dict[str, object]]:
    with request.app.state.db.connect() as conn:
        rows = store.list_jobs(conn, op, status)
    return [_job(row) for row in rows]


@router.get("/jobs/{job_id}")
def get_job(job_id: str, request: Request, _: Reader) -> dict[str, object]:
    with request.app.state.db.connect() as conn:
        row = store.get(conn, job_id)
        if row is None:
            raise NotFound(f"job not found: {job_id}")
        return _job(row, _rolled(conn, job_id))


@router.get("/jobs/{job_id}/children")
def get_children(
    job_id: str, request: Request, _: Reader
) -> list[dict[str, object]]:
    """The child jobs a parent fanned out into."""
    with request.app.state.db.connect() as conn:
        if store.get(conn, job_id) is None:
            raise NotFound(f"job not found: {job_id}")
        return [_job(row) for row in store.children(conn, job_id)]
