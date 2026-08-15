"""The FastAPI application the CLI and dashboard both speak to.

Only the two unauthenticated liveness routes exist today; every other endpoint
arrives with its milestone. ``create_app`` is a factory so tests and future
entry points build isolated apps instead of sharing a module singleton.
"""

from __future__ import annotations

from importlib.metadata import version

from fastapi import APIRouter, FastAPI

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


def create_app() -> FastAPI:
    """Build a fresh hrono server application."""
    app = FastAPI(title="hrono", version=_VERSION)
    app.include_router(router)
    return app
