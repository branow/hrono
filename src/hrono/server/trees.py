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

import json
import sqlite3
from dataclasses import asdict
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel

from hrono.auth.users import User
from hrono.cluster import incubator
from hrono.errors import NotFound
from hrono.export.produce import Export, archive, produce
from hrono.jobs.worker import enqueue
from hrono.recall import log as recall_log
from hrono.recall.ask import ask
from hrono.registry.collections.trees import is_known
from hrono.server.auth import require_role
from hrono.summarize import briefs
from hrono.summarize import store as condensations
from hrono.summarize.resolve import resolve_text_model

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
    require_tree(request, name)
    return _one_build(request, "maintain", name, user.name)


def _one_build(
    request: Request, op: str, tree: str, started_by: str
) -> dict[str, str]:
    """Enqueue ``op`` for ``tree`` — or hand back the one already queued.

    Nothing stopped a double-clicked button or a retried script from queueing
    the same multi-minute, LLM-billed build twice; the duplicates ran back to
    back, each paying for the no-op the other had made of it. One live job per
    (op, tree) is the useful maximum, and answering with its id makes the
    retry idempotent instead of an error.
    """
    with request.app.state.db.connect() as conn:
        row = conn.execute(
            "SELECT id FROM jobs WHERE op = ? AND COALESCE(tree, 'default') "
            "= ? AND status IN ('pending', 'running') AND parent_id IS NULL "
            "ORDER BY created_at LIMIT 1",
            (op, tree),
        ).fetchone()
    if row is not None:
        return {"job_id": str(row["id"])}
    job_id = enqueue(
        request.app.state.db, op, {}, tree=tree, started_by=started_by
    )
    return {"job_id": job_id}


def require_tree(request: Request, name: str) -> None:
    """Refuse a tree nobody registered, before any job is queued."""
    with request.app.state.db.connect() as conn:
        if not is_known(conn, name):
            raise NotFound(
                f"tree not registered: {name}; register it first, or use "
                "`default`"
            )


@router.post("/trees/{name}/sync")
def sync_tree(name: str, request: Request, user: Writer) -> dict[str, str]:
    """Enqueue the incremental chain for ``name`` and return its job id.

    THE operator verb (#137/#138): one call brings an existing tree up to date —
    ingest the diff, re-place what moved, judge what changed, regenerate the
    briefs that are now wrong, measure and repair. `maintain` stays for the
    COLD build of a tree that does not exist yet; the two have very different
    costs and conflating them is how a user pays for a rebuild by accident.
    """
    require_tree(request, name)  # `maintain` checks; this one forgot to
    return _one_build(request, "sync-tree", name, user.name)


@router.post("/trees/{name}/recall")
def recall_tree(
    name: str, body: RecallRequest, request: Request, user: Reader
) -> dict[str, object]:
    """Run the recall engine synchronously and return its ranked hits.

    Each answered call is logged (E042); a call that raises is not.
    """
    database = request.app.state.db
    result = ask(database, name, body.question, body.limit)
    with database.write() as conn:
        recall_log.record(conn, name, user.name, result, body.question)
    return {
        "hits": [asdict(hit) for hit in result.hits],
        "message": result.message,
    }


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
    made = _exported(request, name, levels)
    return {
        "files": [
            {"path": path, "content": made.files[path]}
            for path in sorted(made.files)
        ],
        "shape": asdict(made.shape),
    }


@router.get("/trees/{name}/export.zip")
def export_archive(
    name: str, request: Request, _: Reader, levels: int = _EXPORT_LEVELS
) -> Response:
    """The same export as one zip archive (#205).

    For a browser, which has no folder to write a manifest into and no build
    step to zip one with. The entries are exactly the manifest's files, so the
    archive unpacks to what ``hrono tree export`` writes with the same options.
    """
    made = _exported(request, name, levels)
    return Response(
        archive(made.files),
        media_type="application/zip",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{name}-export-{levels}.zip"'
            )
        },
    )


def _exported(request: Request, name: str, levels: int) -> Export:
    with request.app.state.db.connect() as conn:
        made = produce(conn, name, levels)
    if made is None:
        raise NotFound(f"tree not built: {name}")
    return made


@router.get("/trees/{name}/unusable-briefs")
def unusable_briefs(
    name: str, request: Request, _: Reader
) -> dict[str, object]:
    """Stored briefs that are not briefs (#217, E015).

    The model talking back, or a reply made of its prompt's own words
    (``echoes-the-prompt``); ``why`` names which.

    ``POST /trees/{name}/sync`` rewrites a model's reply and nothing else. A
    settled ``echoes-the-prompt`` stays listed but is not rewritten until its
    members, the brief prompt or the brief model change (E019); this is the
    list to check first.
    """
    with request.app.state.db.connect() as conn:
        found = briefs.unusable_in(conn, name)
    return {
        "count": len(found),
        "briefs": [
            {"node_id": node, "level": level, "why": why, "text": text}
            for node, level, why, text in found
        ],
    }


@router.get("/trees/{name}/unusable-condensations")
def unusable_condensations(
    name: str, request: Request, _: Reader
) -> dict[str, object]:
    """Condensations in this tree that are the model talking back.

    The condense stage treats each as missing, so the next sync re-condenses
    exactly these sections and rewrites the briefs that read them (#221). One
    the model refuses again stays listed — with its last reply, even when
    nothing was ever stored — and is not retried until its body, the condense
    model or the condense prompt changes (E015).
    """
    with request.app.state.db.connect() as conn:
        model = str(resolve_text_model(conn, {}, "condense")["name"])
        found = condensations.unusable(conn, model)
        paths = _paths_in(conn, name, [digest for digest, _, _ in found])
    listed = [
        {"path": path, "content_hash": digest, "why": why, "text": text}
        for digest, why, text in found
        for path in paths.get(digest, ())
    ]
    return {"count": len(listed), "condensations": listed}


def _paths_in(
    conn: sqlite3.Connection, tree: str, digests: list[str]
) -> dict[str, list[str]]:
    """The files in ``tree`` whose sections have each content hash.

    The hashes go in as one JSON parameter: a placeholder each fails past
    SQLite's 32,766-variable limit (E001).
    """
    if not digests:
        return {}
    rows = conn.execute(
        "SELECT DISTINCT s.content_hash AS h, s.path AS path FROM sections s "
        "JOIN node_members m ON m.section_id = s.id "
        "JOIN nodes n ON n.id = m.node_id "
        "WHERE n.tree = ? AND s.content_hash IN "
        "(SELECT value FROM json_each(?)) ORDER BY s.path",
        (tree, json.dumps(digests)),
    ).fetchall()
    found: dict[str, list[str]] = {}
    for row in rows:
        found.setdefault(row["h"], []).append(row["path"])
    return found


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
