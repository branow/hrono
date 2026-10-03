"""The FastAPI application the CLI and dashboard both speak to.

Only the two unauthenticated liveness routes exist today; every other endpoint
arrives with its milestone. ``create_app`` is a factory so tests and future
entry points build isolated apps instead of sharing a module singleton.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse, Response

import hrono.cluster.levels  # noqa: F401 - registers the cluster-briefs op
import hrono.cluster.monitor  # noqa: F401 - registers the monitor op
import hrono.cluster.op  # noqa: F401 - registers the cluster op
import hrono.cluster.repair  # noqa: F401 - registers the repair op
import hrono.embed.op  # noqa: F401 - registers the embed op
import hrono.ingest.split_op  # noqa: F401 - registers the split op
import hrono.ingest.sync  # noqa: F401 - registers the sync op into the registry
import hrono.summarize.brief  # noqa: F401 - registers the brief op
import hrono.summarize.brief_upper  # noqa: F401 - registers the brief-upper op
import hrono.summarize.build_tree  # noqa: F401 - registers the build-tree op
import hrono.summarize.condense  # noqa: F401 - registers the condense op
import hrono.summarize.propagate  # noqa: F401 - registers the propagate op
import hrono.tree.maintain  # noqa: F401 - registers the maintain op
import hrono.tree.settle  # noqa: F401 - registers the settle op
import hrono.tree.sync_chain  # noqa: F401 - registers the sync-tree op
import hrono.tree.update  # noqa: F401 - registers the update op
from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import MasterKeyError, reconcile
from hrono.db.database import DEFAULT_PATH, Database
from hrono.embed.model import resolve_embedding_model
from hrono.embed.runner import start_loading
from hrono.jobs.worker import Worker, reclaim_stranded
from hrono.paths import cache_root
from hrono.registry.collections import COLLECTIONS
from hrono.registry.engine import build_router
from hrono.server.edits import router as edits_router
from hrono.server.errors import install as install_errors
from hrono.server.freshness import Heads
from hrono.server.jobs import router as jobs_router
from hrono.server.trees import router as trees_router
from hrono.server.ui import LoginRequired
from hrono.server.ui import router as ui_router
from hrono.server.usage import router as usage_router
from hrono.server.users import router as users_router

_VERSION = version("hrono")

router = APIRouter()


@router.get("/health")
def health(request: Request) -> JSONResponse:
    """Report whether the server can actually work. Unauthenticated by design.

    Being up is not being healthy: the run that produced #092 stayed up with an
    unusable database and a dead worker. So this probes the database and the
    worker, and answers 503 when either is gone. "The worker" is both of its
    threads (#111): the supervisor that executes jobs AND the reclaimer that
    requeues stranded ones, because a dead reclaimer is exactly the silence
    #093 exists to break.
    """
    database = getattr(request.app.state, "db", None)
    worker = getattr(request.app.state, "worker", None)
    body: dict[str, object] = {
        "status": "ok",
        "database": _probe(database),
        "worker": "alive" if _working(worker) else "dead",
    }
    healthy = body["database"] == {"ok": True, "in_transaction": False}
    if not healthy or body["worker"] != "alive":
        body["status"] = "degraded"
        return JSONResponse(status_code=503, content=body)
    return JSONResponse(status_code=200, content=body)


def _working(worker: object) -> bool:
    """Whether the worker can still do its whole job (#111)."""
    if worker is None:
        return False
    healthy = getattr(worker, "healthy", None)
    return bool(healthy()) if callable(healthy) else False


def _probe(database: Database | None) -> dict[str, object]:
    if database is None:
        return {"ok": False, "error": "no database"}
    try:
        return database.probe()
    except Exception as exc:  # noqa: BLE001 - any driver failure is unhealthy
        return {"ok": False, "error": type(exc).__name__}


@router.get("/version")
def report_version() -> dict[str, str]:
    """Report the running build. Unauthenticated by design."""
    return {"name": "hrono", "version": _VERSION}


_logger = logging.getLogger("hrono")


def _warm_query_encoder(database: Database) -> None:
    """Load the query encoder in the background while the server boots (#168).

    Recall's first request paid 13.3s to read the model's weights and every
    later one 14ms, which is the whole cost sitting on one arbitrary user's
    question. Loading here moves it off the request path entirely.

    The DATABASE is read here, on the startup thread, and only the weights are
    read in the background. The first version read the config inside the thread
    and that was wrong: an adopted connection is lent to one thread at a time
    by ``Shared``'s lock, but a caller holding the raw connection — every test
    that writes through ``with conn:`` — is not going through that lock, so a
    background reader could be executing on the same sqlite3 connection at the
    same moment. Nothing needs the database off the request path; only the
    weights are slow.

    Never fatal: a server with no embedding model registered yet is perfectly
    valid and must still start, and a model that cannot load is a problem for
    the request that needs it to report, not for startup to die of.

    The background load itself is ``runner.start_loading``, which recall also
    calls on a miss (#169) — one loader, so a question arriving mid-boot joins
    the load already running rather than starting a second one.
    """
    try:
        with database.connect() as conn:
            model_id = str(resolve_embedding_model(conn, {})["model"])
    except Exception:  # noqa: BLE001 - a cold cache is not a failed boot
        _logger.debug("query encoder not warmed", exc_info=True)
        return

    start_loading(model_id)


def create_app(
    *,
    db_path: Path = DEFAULT_PATH,
    connection: sqlite3.Connection | None = None,
    master_key: bytes | None = None,
    key_id: int | None = None,
) -> FastAPI:
    """Build a fresh hrono server application.

    The database is opened and migrated on startup, before requests are served,
    and closed on shutdown. Pass ``db_path`` to open and reconcile the file
    here, or ``connection`` to supply a connection whose key is already
    reconciled by the caller (with its ``key_id``); an injected connection is
    used as-is and left for its owner to close. The ``master_key`` is required
    at startup and is held in app state (never logged, never persisted) for the
    cipher to use. ``app.state.db`` lends a connection per operation, so one
    failed op cannot leave the next one wedged, and jobs left ``running`` by a
    previous process go back on the queue before the worker starts.

    The ingest cache hangs off ``db_path`` (#098), so an app built from an
    injected ``connection`` has no cache root and its worker refuses ingest ops
    instead of resolving one against the working directory.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = connection is None
        database = (
            Database.at(db_path)
            if connection is None
            else Database.adopt(connection)
        )
        app.state.db = database
        worker: Worker | None = None
        try:
            if master_key is None:
                raise MasterKeyError("master key required to start the server")
            if owned:
                with database.write() as active:
                    active_id = reconcile(active, master_key).key_id
            else:
                active_id = key_id
            cipher = Cipher.from_key(master_key, active_id)
            app.state.cipher = cipher
            reclaim_stranded(database)
            anchored_cache = cache_root(db_path) if owned else None
            worker = Worker(
                database,
                cipher=cipher,
                # an injected connection says nothing about where its file is,
                # so there is no anchor to hang a cache on: None makes an
                # ingest op raise rather than guess a cwd-relative one (#098).
                cache_root=anchored_cache,
            )
            app.state.worker = worker
            app.state.cache_root = anchored_cache
            worker.start()
            _warm_query_encoder(database)
            yield
        finally:
            if worker is not None:
                worker.stop()
                worker.join(timeout=5)
            if owned:
                database.close()

    app = FastAPI(title="hrono", version=_VERSION, lifespan=lifespan)
    app.state.heads = Heads()
    install_errors(app)

    @app.exception_handler(LoginRequired)
    def _to_login(request: Request, exc: Exception) -> Response:
        """A browser gets the login page where an API caller gets a 401."""
        return RedirectResponse("/ui/login", status_code=303)

    app.include_router(router)
    app.include_router(users_router)
    app.include_router(jobs_router)
    app.include_router(usage_router)
    app.include_router(trees_router)
    app.include_router(edits_router)
    app.include_router(ui_router)
    for descriptor in COLLECTIONS:
        app.include_router(build_router(descriptor))
    return app
