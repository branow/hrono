"""Tree routes: kick a tree's work (writer+) and read what it holds.

``POST /trees/{name}/sync`` is the operator verb: it enqueues the incremental
chain (#137) that brings an existing tree up to date.
``POST /trees/{name}/maintain`` enqueues a maintain job for the named tree and
returns its id; the background worker runs the ordered pipeline. Writing this
does the work of a job, so it is a POST behind the writer role, and it returns
only the job id to track — config-vs-work stays separated.
``GET /trees/{name}/pending`` reads the incubator pool (#086) so chunks waiting
outside the tree are visible rather than silently missing from the map.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from hrono import notes
from hrono.auth.users import User
from hrono.cluster import incubator
from hrono.embed.model import resolve_embedding_model
from hrono.embed.runner import Encoder, ready_encoder_for
from hrono.errors import NotFound, Unavailable
from hrono.export import store as export_store
from hrono.export.collapse import collapse, shape
from hrono.export.render import render
from hrono.jobs.worker import enqueue
from hrono.recall import engine
from hrono.server.auth import require_role

_EXPORT_LEVELS = 4

router = APIRouter()

Writer = Annotated[User, Depends(require_role("writer"))]
Reader = Annotated[User, Depends(require_role("reader"))]


class RecallRequest(BaseModel):
    question: str
    limit: int = 10


@router.post("/trees/{name}/maintain")
def maintain_tree(name: str, request: Request, user: Writer) -> dict[str, str]:
    """Enqueue a maintain job for ``name`` and return its job id."""
    job_id = enqueue(
        request.app.state.db, "maintain", {}, tree=name, started_by=user.name
    )
    return {"job_id": job_id}


@router.post("/trees/{name}/sync")
def sync_tree(name: str, request: Request, user: Writer) -> dict[str, str]:
    """Enqueue the incremental chain for ``name`` and return its job id.

    THE operator verb (#137/#138): one call brings an existing tree up to date —
    ingest the diff, re-place what moved, judge what changed, regenerate the
    briefs that are now wrong, measure and repair. `maintain` stays for the
    COLD build of a tree that does not exist yet; the two have very different
    costs and conflating them is how a user pays for a rebuild by accident.
    """
    job_id = enqueue(
        request.app.state.db, "sync-tree", {}, tree=name, started_by=user.name
    )
    return {"job_id": job_id}


@router.post("/trees/{name}/recall")
def recall_tree(
    name: str, body: RecallRequest, request: Request, _: Reader
) -> dict[str, object]:
    """Run the recall engine synchronously and return its ranked hits."""
    database = request.app.state.db
    with database.connect() as conn:
        model = resolve_embedding_model(conn, {})
    encode = _query_encode(str(model["model"]))
    with database.connect() as conn:
        result = engine.recall(
            conn,
            body.question,
            str(model["name"]),
            encode,
            limit=body.limit,
            tree=name,
        )
    return {
        "hits": [asdict(hit) for hit in result.hits],
        "message": result.message,
    }


def _query_encode(model_id: str) -> Encoder:
    """The query encoder, if it is ready; otherwise say so and do not wait.

    A question has someone waiting on it, so it does not queue behind a load it
    cannot see — it reports that the model is still arriving and asks them back
    (#169). The miss starts the load, so "shortly" is true rather than
    hopeful.
    """
    encoder = ready_encoder_for(model_id)
    if encoder is None:
        raise Unavailable(
            f"the embedding model is still loading ({model_id}); "
            f"recall will answer once it is in memory"
        )
    return encoder


@router.get("/trees/{name}/export")
def export_tree(
    name: str, request: Request, _: Reader, levels: int = _EXPORT_LEVELS
) -> dict[str, object]:
    """Return the rendered agent-facing tree as a path -> content manifest.

    ``levels`` is the hop limit, the links an agent follows from ``root.md``
    to a section (default 4); #078 floors it at 2, so ``levels`` below 2
    yields a 2-level export rather than an error. ``shape`` says what came out
    (#204): pages per level and the widest page against the width budget. A
    non-integer ``levels`` is a clean 422 (FastAPI validation); an unbuilt tree
    is a clean 404.
    """
    database = request.app.state.db
    with database.connect() as conn:
        stored = export_store.load(conn, name)
        if stored is None:
            raise NotFound(f"tree not built: {name}")
        agent_tree = collapse(stored, levels)
        files = render(conn, agent_tree, notes=notes.rendered(conn, notes.NODE))
    return {
        "files": [
            {"path": path, "content": files[path]} for path in sorted(files)
        ],
        "shape": asdict(shape(agent_tree)),
    }


@router.get("/trees/{name}/pending")
def pending_tree(name: str, request: Request, _: Reader) -> dict[str, object]:
    """Return the incubator pool: chunks parked in no node yet (#086).

    A parked chunk is in the corpus but not on the map, so the pool has to be
    visible; an empty pool (or an unbuilt tree) is a plain zero, not a 404.
    """
    with request.app.state.db.connect() as conn:
        pool = incubator.pending(conn, name)
    return {
        "count": len(pool),
        "pending": [
            {
                "section_id": section_id,
                "content_hash": digest,
                "path": path,
                "batch": batch,
            }
            for section_id, digest, path, batch in pool
        ],
    }
