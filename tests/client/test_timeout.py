"""A slow server is not a missing one.

A timeout must not read as "Cannot reach hrono server": that sends the user to
check a process that is working and merely slow, so `TimedOut` is its own
error, apart from `Unreachable` (connection refused, DNS).
"""

from __future__ import annotations

import httpx
import pytest

from hrono.client.http import Client, TimedOut, Unreachable, message


def _client(handler: object, *, timeout: float = 10.0) -> Client:
    transport = httpx.MockTransport(handler)  # type: ignore[arg-type]
    http = httpx.Client(transport=transport, base_url="http://server")
    return Client("http://server", "t", http=http, timeout=timeout)


def test_a_slow_server_times_out_rather_than_reading_as_unreachable() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(TimedOut) as caught:
        _client(slow).get("/anything")

    assert caught.value.seconds == 10.0
    assert caught.value.server_url == "http://server"


def test_a_refused_connection_is_still_unreachable() -> None:
    # the other half: the two must not collapse back into one message, because
    # they send the reader to different places.
    def refused(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(Unreachable):
        _client(refused).get("/anything")


def test_the_two_messages_say_different_things() -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(TimedOut) as timed:
        _client(slow, timeout=42.0).get("/anything")

    text = message(timed.value)
    assert "42s" in text
    assert "running" in text  # it tells them the server is alive
    assert "Cannot reach" not in text


def test_a_per_request_budget_overrides_the_client_default() -> None:
    # recall needs a budget of its own: the 10s default was chosen for registry
    # CRUD and a cold recall exceeds it.
    seen: list[float | None] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request.extensions.get("timeout", {}).get("read"))
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(record)
    client = Client("http://server", "t", timeout=10.0)
    client._http = httpx.Client(  # noqa: SLF001 - the injection seam
        transport=transport, base_url="http://server", timeout=99.0
    )
    client.post("/trees/t/recall", {"question": "q"}, timeout=99.0)

    assert seen == [99.0]


def test_a_write_budget_reaches_the_request() -> None:
    # the per-request budget must be on the wire, injected client or not.
    seen: list[float | None] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request.extensions.get("timeout", {}).get("read"))
        return httpx.Response(200, json={})

    _client(record).put("/models/m", {"name": "m"}, timeout=120.0)

    assert seen == [120.0]


@pytest.mark.parametrize(
    ("check", "expected"),
    [
        pytest.param(
            "hrono models get m",
            "check with 'hrono models get m'",
            id="a-write-names-its-check",
        ),
        pytest.param(None, None, id="a-read-has-nothing-to-check"),
    ],
)
def test_a_timeout_says_how_to_see_whether_a_write_landed(
    check: str | None, expected: str | None
) -> None:
    def slow(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("too slow", request=request)

    with pytest.raises(TimedOut) as timed:
        _client(slow).put("/models/m", {"name": "m"}, check=check)

    text = message(timed.value)
    assert "running" in text
    if expected is None:
        assert "check with" not in text
    else:
        assert expected in text
