"""One HTTP GET/POST for every API-backed source type.

Discovery and page sources all need the same three things from a provider
call: a status, a parsed body, and a transport failure that arrives as a
``SyncError`` with no credential in it. That is all this is. Response handling
stays with each provider, because only it knows what a 404 means.
"""

from __future__ import annotations

import httpx

from hrono.ingest import SyncError

TIMEOUT = 30.0


def get_json(
    url: str, headers: dict[str, str], timeout: float = TIMEOUT
) -> tuple[int, object]:
    """GET ``url``; return (status, parsed body or None)."""
    return _send("GET", url, headers, None, timeout)


def post_json(
    url: str,
    headers: dict[str, str],
    body: dict[str, object],
    timeout: float = TIMEOUT,
) -> tuple[int, object]:
    """POST ``body`` as JSON; return (status, parsed body or None)."""
    return _send("POST", url, headers, body, timeout)


def _send(
    method: str,
    url: str,
    headers: dict[str, str],
    body: dict[str, object] | None,
    timeout: float,
) -> tuple[int, object]:
    try:
        response = httpx.request(
            method, url, headers=headers, json=body, timeout=timeout
        )
    except httpx.HTTPError as exc:
        # the type, never the text: a url with userinfo in it would otherwise
        # reach a job record through the message
        raise SyncError(
            f"cannot reach the provider: {type(exc).__name__}"
        ) from exc
    try:
        return response.status_code, response.json()
    except ValueError:
        return response.status_code, None
