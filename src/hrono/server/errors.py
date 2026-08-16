"""The one exception-handling layer: map any domain error, log, never leak.

Registered in ``create_app``. An ``AppError`` renders from its own metadata; any
other uncaught exception becomes a generic 500 whose body carries no internal
detail — the traceback is only logged.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from hrono.errors import AppError, envelope

_logger = logging.getLogger("hrono")

_INTERNAL = {
    "error": {
        "code": "internal-error",
        "message": "internal error",
        "details": None,
    }
}


def install(app: FastAPI) -> None:
    """Register the AppError and catch-all handlers on the app."""
    app.add_exception_handler(AppError, _handle_app_error)
    app.add_exception_handler(Exception, _handle_unexpected)


def _handle_app_error(request: Request, exc: Exception) -> JSONResponse:
    error = exc if isinstance(exc, AppError) else AppError("internal error")
    if error.status_code >= 500:
        _logger.error("%s", error.code, exc_info=error)
    else:
        _logger.warning("%s: %s", error.code, error.message)
    return JSONResponse(
        status_code=error.status_code,
        content=envelope(error),
        headers=error.headers,
    )


def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    _logger.error("internal-error", exc_info=exc)
    return JSONResponse(status_code=500, content=_INTERNAL)
