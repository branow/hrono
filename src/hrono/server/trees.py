"""Tree routes: kick the whole-pipeline ``maintain`` job (writer+).

``POST /trees/{name}/maintain`` enqueues a maintain job for the named tree and
returns its id; the background worker runs the ordered pipeline. Writing this
does the work of a job, so it is a POST behind the writer role, and it returns
only the job id to track — config-vs-work stays separated.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from hrono.auth.users import User
from hrono.jobs.worker import enqueue
from hrono.server.auth import require_role

router = APIRouter()

Writer = Annotated[User, Depends(require_role("writer"))]


@router.post("/trees/{name}/maintain")
def maintain_tree(name: str, request: Request, _: Writer) -> dict[str, str]:
    """Enqueue a maintain job for ``name`` and return its job id."""
    job_id = enqueue(request.app.state.db, "maintain", {}, tree=name)
    return {"job_id": job_id}
