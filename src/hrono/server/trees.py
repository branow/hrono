"""Tree routes: kick the whole-pipeline ``maintain`` job (writer+).

``POST /trees/{name}/maintain`` enqueues a maintain job for the named tree and
returns its id; the background worker runs the ordered pipeline. Writing this
does the work of a job, so it is a POST behind the writer role, and it returns
only the job id to track — config-vs-work stays separated.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from hrono.auth.users import User
from hrono.embed.model import resolve_embedding_model
from hrono.embed.runner import Encoder, encoder_for
from hrono.jobs.worker import enqueue
from hrono.recall import engine
from hrono.server.auth import require_role

router = APIRouter()

Writer = Annotated[User, Depends(require_role("writer"))]
Reader = Annotated[User, Depends(require_role("reader"))]


class RecallRequest(BaseModel):
    question: str
    limit: int = 10


@router.post("/trees/{name}/maintain")
def maintain_tree(name: str, request: Request, _: Writer) -> dict[str, str]:
    """Enqueue a maintain job for ``name`` and return its job id."""
    job_id = enqueue(request.app.state.db, "maintain", {}, tree=name)
    return {"job_id": job_id}


@router.post("/trees/{name}/recall")
def recall_tree(
    name: str, body: RecallRequest, request: Request, _: Reader
) -> dict[str, object]:
    """Run the recall engine synchronously and return its ranked hits."""
    database = request.app.state.db
    with database.connect() as conn:
        model = resolve_embedding_model(conn, {})
    encode = _query_encode(str(model["model"]))  # loads the model off the lock
    with database.connect() as conn:
        result = engine.recall(
            conn, body.question, str(model["name"]), encode, limit=body.limit
        )
    return {
        "hits": [asdict(hit) for hit in result.hits],
        "message": result.message,
    }


def _query_encode(model_id: str) -> Encoder:
    """Build the query encoder for a model (overridable in tests)."""
    return encoder_for(model_id)
