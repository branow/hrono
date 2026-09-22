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
from hrono.jobs.model import to_job
from hrono.jobs.ops import OPS
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


def _job(row: sqlite3.Row) -> dict[str, object]:
    job = to_job(row)
    return {
        "id": job.id,
        "parent_id": job.parent_id,
        "tree": job.tree,
        "op": job.op,
        "scope": job.scope,
        "status": job.status,
        "error": job.error,
        "result": job.result,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


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
    job_id = enqueue(request.app.state.db, body.op, body.scope, tree=body.tree)
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
    return _job(row)
