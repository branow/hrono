"""Domain errors that carry their own mapping metadata.

Code everywhere just raises an ``AppError`` subclass; one server handler renders
any of them into the HTTP envelope, and the CLI boundary renders the same
metadata to a one-line message. Adding an error is a subclass with baked
metadata — never a change to a handler or a hand-kept error dictionary.

Envelope (settled here; the spec is silent): ``{"error": {"code": <kebab-case>,
"message": <client-safe>, "details": {...} | null}}``.
"""

from __future__ import annotations


class AppError(Exception):
    """Base domain error; subclasses bake status_code + code."""

    status_code: int = 500
    code: str = "internal-error"
    headers: dict[str, str] | None = None

    def __init__(
        self, message: str, *, details: dict[str, object] | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details


class BadRequest(AppError):
    status_code = 400
    code = "bad-request"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"
    headers = {"WWW-Authenticate": "Bearer"}


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class NotFound(AppError):
    status_code = 404
    code = "not-found"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class Invalid(AppError):
    status_code = 422
    code = "validation-error"


def envelope(error: AppError) -> dict[str, object]:
    """Render an AppError into the HTTP error envelope from its own metadata."""
    return {
        "error": {
            "code": error.code,
            "message": error.message,
            "details": error.details,
        }
    }


def cli_message(error: AppError) -> str:
    """Render an AppError to a one-line, client-safe CLI message."""
    return error.message
