"""Domain errors that carry their own mapping metadata.

Code everywhere just raises an ``AppError`` subclass; one server handler renders
any of them into the HTTP envelope, and the CLI boundary renders the same
metadata to a one-line message. Adding an error is a subclass with baked
metadata — never a change to a handler or a hand-kept error dictionary.

Envelope (settled here; the spec is silent): ``{"error": {"code": <kebab-case>,
"message": <client-safe>, "details": {...} | null}}``.
"""

from __future__ import annotations


class DomainError(Exception):
    """A failure inside hrono, carrying its own kebab-case ``code``.

    These live in the package that raises them — ``SyncError`` in ``ingest``,
    ``ClusterError`` in ``cluster`` — and know nothing about transport. This
    base exists here, in the module that imports nothing, so every package can
    inherit it without a cycle, and so a boundary can tell "hrono failed, and
    this is which failure" from "something threw".

    ``code`` is the whole contract. A subclass that forgets to set one is a
    bug, and the test that walks the subclasses says so.
    """

    code: str = "internal-error"


class AppError(Exception):
    """Base domain error; subclasses bake status_code + code."""

    status_code: int = 500
    code: str = "internal-error"
    headers: dict[str, str] | None = None

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, object] | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if code is not None:
            # a per-instance override, for a boundary relaying a DomainError's
            # own code through a generic AppError class
            self.code = code


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


class Internal(AppError):
    status_code = 500
    code = "internal-error"


class Unavailable(AppError):
    status_code = 503
    code = "unavailable"


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


def as_app_error(error: BaseException) -> AppError:
    """Any exception as an ``AppError``, so a failure has a CODE.

    An ``AppError`` already carries one, and a ``DomainError`` carries the one
    its own class declares. Anything else raised from hrono's own code
    keeps its message under ``internal-error`` — it is hrono speaking,
    already written for a reader, and keeps its message. A FOREIGN exception is
    the one whose wording must not become hrono's answer: sqlite's
    ``RAISE(ABORT, 'poisoned mid-transaction')`` is the driver's phrasing, and
    a client reading it would be reading our storage engine's internals. Those
    keep only their type, and the wording reaches the log instead.

    Every unmapped failure is ``internal-error``. Giving each domain error its
    own code is a separate mapping layer's job; this is the
    boundary that guarantees there is always a code to begin with.
    """
    if isinstance(error, AppError):
        return error
    details: dict[str, object] = {"type": type(error).__name__}
    if isinstance(error, DomainError):
        return Internal(str(error), details=details, code=error.code)
    if type(error).__module__.startswith("hrono."):
        return Internal(str(error), details=details)
    return Internal("the job failed", details=details)
