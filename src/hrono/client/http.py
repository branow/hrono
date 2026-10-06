"""The shared HTTP client every CLI subcommand talks to ``hrono serve`` through.

Resolves the current profile (server_url + token), attaches the Bearer token on
every request, and maps transport/HTTP failures to typed errors the CLI boundary
renders as a clean one-line message. The token never appears in a message,
exception, or log line.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import httpx

from hrono.profile.store import Store, config_path


class ClientError(Exception):
    """Base for client-side failures; the boundary maps it to a clean line."""


class NoProfile(ClientError):
    """No profile is current, so there is no server to talk to."""


class Unreachable(ClientError):
    """The server could not be reached (connection refused, DNS)."""

    def __init__(self, server_url: str) -> None:
        super().__init__("unreachable")
        self.server_url = server_url


class TimedOut(ClientError):
    """The server was reached and did not answer inside the budget (#168).

    Its own type because it sends the reader somewhere else entirely: an
    unreachable server is not running, and a timed-out one is working. Told
    "cannot reach", an operator goes to check a process that is fine.
    """

    def __init__(
        self, server_url: str, seconds: float, *, check: str | None = None
    ) -> None:
        super().__init__("timed out")
        self.server_url = server_url
        self.seconds = seconds
        self.check = check


class Unauthorized(ClientError):
    """The server rejected the token (401)."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(detail or "unauthorized")
        self.detail = detail


class Forbidden(ClientError):
    """The token's role lacks permission (403)."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(detail or "forbidden")
        self.detail = detail


class NotFound(ClientError):
    """The resource does not exist (404)."""

    def __init__(self, detail: str = "") -> None:
        super().__init__(detail or "not found")
        self.detail = detail


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

    def get(self, path: str, *, timeout: float | None = None) -> object:
        return self._request("GET", path, None, timeout)

    def post(
        self,
        path: str,
        body: dict[str, object],
        *,
        timeout: float | None = None,
    ) -> object:
        return self._request("POST", path, body, timeout)

    def stream(self, path: str) -> Iterator[str]:
        """Yield each line of a streaming response (SSE).

        Its own method because the JSON path cannot serve it: `_request`
        decodes a whole body, and a stream has no whole body until the job it
        is watching finishes. No read timeout either — a watch is meant to sit
        there quietly, and the 10s that suits registry CRUD would end it
        mid-job (#168's lesson, one endpoint over).
        """
        headers = {"Authorization": f"Bearer {self._token}"}
        timeout = httpx.Timeout(None, connect=self._timeout)
        try:
            with (
                httpx.Client(base_url=self._base, timeout=timeout) as http,
                http.stream("GET", path, headers=headers) as response,
            ):
                if response.status_code >= 400:
                    response.read()
                    raise _error(response)
                yield from response.iter_lines()
        except httpx.ConnectTimeout as exc:
            raise Unreachable(self._base) from exc
        except httpx.TimeoutException as exc:
            raise TimedOut(self._base, self._timeout) from exc
        except httpx.HTTPError as exc:
            raise Unreachable(self._base) from exc

    def put(
        self,
        path: str,
        body: dict[str, object],
        *,
        timeout: float | None = None,
        check: str | None = None,
    ) -> object:
        """Write ``body``; ``check`` is the command a timeout tells the reader
        to run, since a write that timed out may still have landed (E003)."""
        return self._request("PUT", path, body, timeout, check)

    def delete(self, path: str) -> object:
        return self._request("DELETE", path, None, None)

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, object] | None,
        timeout: float | None,
        check: str | None = None,
    ) -> object:
        headers = {"Authorization": f"Bearer {self._token}"}
        budget = self._timeout if timeout is None else timeout
        try:
            response = self._send(method, path, body, headers, budget)
        except httpx.ConnectTimeout as exc:
            # a CONNECT timeout means nothing answered the socket at all --
            # reporting it as "running, just slow" sent operators to watch a
            # server that was down or firewalled.
            raise Unreachable(self._base) from exc
        except httpx.TimeoutException as exc:
            raise TimedOut(self._base, budget, check=check) from exc
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
        timeout: float,
    ) -> httpx.Response:
        if self._http is not None:
            return self._http.request(
                method, path, json=body, headers=headers, timeout=timeout
            )
        with httpx.Client(base_url=self._base, timeout=timeout) as http:
            return http.request(method, path, json=body, headers=headers)


def from_profile() -> Client:
    """Build a client for the current profile; raise ``NoProfile`` if none."""
    current = Store(config_path()).current()
    if current is None:
        raise NoProfile
    return Client(current.server_url, current.token)


def _error(response: httpx.Response) -> ClientError:
    """A typed error that KEEPS the server's own message.

    The envelope's message used to be thrown away for 401/403/404, so every
    missing tree, job or model printed exactly "Not found." — and a profile
    pointed at something that is not a hrono server looked identical to a
    missing resource.
    """
    factory = _STATUS_ERRORS.get(response.status_code)
    if factory is not None:
        return factory(_detail(response))
    return RequestFailed(response.status_code, _detail(response))


def _detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except ValueError:
        return f"request failed ({response.status_code})"
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return f"request failed ({response.status_code})"
    message = error.get("message")
    if not isinstance(message, str):
        return f"request failed ({response.status_code})"
    fields = _fields(error.get("details"))
    return message if not fields else message + "\n" + "\n".join(fields)


def _fields(details: object) -> list[str]:
    """The per-field reasons a validation failure carries, one line each.

    The server has always sent these and the CLI has always dropped them, so a
    config with a missing field printed exactly "invalid body" and nothing a
    person could act on. The shape is pydantic's: `loc` is the path to the
    field, `msg` is what is wrong with it.
    """
    if not isinstance(details, dict):
        return []
    errors = details.get("errors")
    if not isinstance(errors, list):
        return []
    lines = []
    for item in errors:
        if not isinstance(item, dict):
            continue
        where = ".".join(str(part) for part in item.get("loc", ())) or "body"
        why = str(item.get("msg", "is not valid"))
        lines.append(f"  {where}: {why}")
    return lines


def message(error: ClientError) -> str:
    """Render a client error as a clean, token-free one-line CLI message."""
    builder = _MESSAGES.get(type(error))
    if builder is not None:
        return builder(error)
    if isinstance(error, RequestFailed):
        return error.detail
    return str(error)


_STATUS_ERRORS: dict[int, Callable[[str], ClientError]] = {
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
        f"Cannot reach hrono server at {e.server_url}. "  # type: ignore[attr-defined]
        "Is 'hrono serve' running? 'hrono profile current' shows which "
        "server this profile points at."
    ),
    TimedOut: lambda e: _timed_out(e),  # type: ignore[arg-type]
    Unauthorized: lambda e: (
        "Unauthorized — this profile's token was rejected. Update it with "
        "'hrono profile set-token <name>'; if the token is lost, reissue one "
        "with 'hrono admin reset-token <user>' on the server machine."
    ),
    Forbidden: lambda e: (
        "Forbidden — this token's role lacks permission for that."
    ),
    NotFound: lambda e: _not_found(e),  # type: ignore[arg-type]
}


def _not_found(error: NotFound) -> str:
    """The server's own sentence when it sent one; a bare 404 otherwise."""
    detail = error.detail
    if detail and not detail.startswith("request failed"):
        return detail
    return (
        "Not found — the server answered 404 without saying what is missing. "
        "Is this profile's URL really a hrono server?"
    )


def _timed_out(error: TimedOut) -> str:
    """A slow answer; for a write, also how to see whether it landed (E003).

    A write that timed out may still have been applied, and retrying one that
    succeeded is how someone ends up with two of something — so the reader is
    told what to run instead of being left to guess.
    """
    line = (
        f"hrono server at {error.server_url} did not answer within "
        f"{error.seconds:g}s. It is running — the request is just slow."
    )
    if error.check is None:
        return line
    return f"{line} It may have landed; check with '{error.check}'."
