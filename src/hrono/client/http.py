"""The shared HTTP client every CLI subcommand talks to ``hrono serve`` through.

Resolves the current profile (server_url + token), attaches the Bearer token on
every request, and maps transport/HTTP failures to typed errors the CLI boundary
renders as a clean one-line message. The token never appears in a message,
exception, or log line.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx

from hrono.profile.store import Store, config_path


class ClientError(Exception):
    """Base for client-side failures; the boundary maps it to a clean line."""


class NoProfile(ClientError):
    """No profile is current, so there is no server to talk to."""


class Unreachable(ClientError):
    """The server could not be reached (connection refused / DNS / timeout)."""

    def __init__(self, server_url: str) -> None:
        super().__init__("unreachable")
        self.server_url = server_url


class Unauthorized(ClientError):
    """The server rejected the token (401)."""


class Forbidden(ClientError):
    """The token's role lacks permission (403)."""


class NotFound(ClientError):
    """The resource does not exist (404)."""


class RequestFailed(ClientError):
    """Any other 4xx/5xx; carries the server's message when present."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


class Client:
    """Issues authenticated JSON requests against one server."""

    def __init__(
        self,
        server_url: str,
        token: str,
        *,
        http: httpx.Client | None = None,
        timeout: float = 10.0,
    ) -> None:
        self._base = server_url.rstrip("/")
        self._token = token
        self._http = http
        self._timeout = timeout

    def get(self, path: str) -> object:
        return self._request("GET", path, None)

    def post(self, path: str, body: dict[str, object]) -> object:
        return self._request("POST", path, body)

    def put(self, path: str, body: dict[str, object]) -> object:
        return self._request("PUT", path, body)

    def delete(self, path: str) -> object:
        return self._request("DELETE", path, None)

    def _request(
        self, method: str, path: str, body: dict[str, object] | None
    ) -> object:
        headers = {"Authorization": f"Bearer {self._token}"}
        try:
            response = self._send(method, path, body, headers)
        except httpx.HTTPError as exc:
            raise Unreachable(self._base) from exc
        if response.status_code >= 400:
            raise _error(response)
        return response.json() if response.content else None

    def _send(
        self,
        method: str,
        path: str,
        body: dict[str, object] | None,
        headers: dict[str, str],
    ) -> httpx.Response:
        if self._http is not None:
            return self._http.request(method, path, json=body, headers=headers)
        with httpx.Client(base_url=self._base, timeout=self._timeout) as http:
            return http.request(method, path, json=body, headers=headers)


def from_profile() -> Client:
    """Build a client for the current profile; raise ``NoProfile`` if none."""
    current = Store(config_path()).current()
    if current is None:
        raise NoProfile
    return Client(current.server_url, current.token)


def _error(response: httpx.Response) -> ClientError:
    factory = _STATUS_ERRORS.get(response.status_code)
    if factory is not None:
        return factory()
    return RequestFailed(response.status_code, _detail(response))


def _detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"request failed ({response.status_code})"
    error = payload.get("error") if isinstance(payload, dict) else None
    message = error.get("message") if isinstance(error, dict) else None
    if isinstance(message, str):
        return message
    return f"request failed ({response.status_code})"


def message(error: ClientError) -> str:
    """Render a client error as a clean, token-free one-line CLI message."""
    builder = _MESSAGES.get(type(error))
    if builder is not None:
        return builder(error)
    if isinstance(error, RequestFailed):
        return error.detail
    return str(error)


_STATUS_ERRORS: dict[int, Callable[[], ClientError]] = {
    401: Unauthorized,
    403: Forbidden,
    404: NotFound,
}

_MESSAGES: dict[type[ClientError], Callable[[ClientError], str]] = {
    NoProfile: lambda _: (
        "No active profile. Add one with "
        "'hrono profile add <name> --server <url> --token <token>'."
    ),
    Unreachable: lambda e: (
        f"Cannot reach hrono server at {e.server_url}."  # type: ignore[attr-defined]
    ),
    Unauthorized: lambda _: "Unauthorized — check the token for this profile.",
    Forbidden: lambda _: "Forbidden — this token's role lacks permission.",
    NotFound: lambda _: "Not found.",
}
