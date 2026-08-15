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

from hrono.db.database import DEFAULT_PATH, open_database

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
) -> FastAPI:
    """Build a fresh hrono server application.

    The database is opened and migrated on startup, before requests are served,
    and closed on shutdown. Pass ``db_path`` to relocate the file or
    ``connection`` to supply a ready connection (tests inject either); an
    injected connection is used as-is and left for its owner to close.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = connection is None
        conn = open_database(db_path) if owned else connection
        app.state.db = conn
        try:
            yield
        finally:
            if owned:
                conn.close()

    app = FastAPI(title="hrono", version=_VERSION, lifespan=lifespan)
    app.include_router(router)
    return app
