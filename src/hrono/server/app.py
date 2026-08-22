"""The FastAPI application the CLI and dashboard both speak to.

Only the two unauthenticated liveness routes exist today; every other endpoint
arrives with its milestone. ``create_app`` is a factory so tests and future
entry points build isolated apps instead of sharing a module singleton.
"""

from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version
from pathlib import Path

from fastapi import APIRouter, FastAPI

import hrono.cluster.op  # noqa: F401 - registers the cluster op
import hrono.embed.op  # noqa: F401 - registers the embed op
import hrono.ingest.split_op  # noqa: F401 - registers the split op
import hrono.ingest.sync  # noqa: F401 - registers the sync op into the registry
from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import MasterKeyError, reconcile
from hrono.db.database import DEFAULT_PATH, Database, open_database
from hrono.jobs.worker import Worker
from hrono.registry.collections import COLLECTIONS
from hrono.registry.engine import build_router
from hrono.server.errors import install as install_errors
from hrono.server.jobs import router as jobs_router
from hrono.server.users import router as users_router

_VERSION = version("hrono")

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    """Report that the server is up. Unauthenticated by design."""
    return {"status": "ok"}


@router.get("/version")
def report_version() -> dict[str, str]:
    """Report the running build. Unauthenticated by design."""
    return {"name": "hrono", "version": _VERSION}


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
    cipher to use. ``app.state.db`` is a ``Database`` owner that serializes
    access so sync route handlers can use the connection safely.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = connection is None
        conn = open_database(db_path) if owned else connection
        database = Database(conn)
        app.state.db = database
        worker: Worker | None = None
        try:
            if master_key is None:
                raise MasterKeyError("master key required to start the server")
            app.state.master_key = master_key
            if owned:
                with database.connect() as active:
                    app.state.key_id = reconcile(active, master_key).key_id
            else:
                app.state.key_id = key_id
            cipher = Cipher.from_key(master_key, app.state.key_id)
            worker = Worker(database, cipher=cipher)
            app.state.worker = worker
            worker.start()
            yield
        finally:
            if worker is not None:
                worker.stop()
                worker.join(timeout=5)
            if owned:
                database.close()

    app = FastAPI(title="hrono", version=_VERSION, lifespan=lifespan)
    install_errors(app)
    app.include_router(router)
    app.include_router(users_router)
    app.include_router(jobs_router)
    for descriptor in COLLECTIONS:
        app.include_router(build_router(descriptor))
    return app
