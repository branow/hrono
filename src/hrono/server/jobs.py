"""Read-only jobs routes: list and fetch job status (reader+)."""

from __future__ import annotations

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from hrono.auth.users import User
from hrono.jobs import store
from hrono.jobs.model import to_job
from hrono.server.auth import require_role

router = APIRouter()

Reader = Annotated[User, Depends(require_role("reader"))]


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
        "created_at": job.created_at,
        "updated_at": job.updated_at,
    }


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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"job not found: {job_id}",
        )
    return _job(row)
