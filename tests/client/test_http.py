from pathlib import Path

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.client.http import (
    Client,
    Forbidden,
    NoContext,
    NotFound,
    RequestFailed,
    Unauthorized,
    Unreachable,
    from_context,
    message,
)
from hrono.server.app import create_app

TOKEN = "sekret-bearer-token"


def mock_client(handler: object) -> httpx.Client:
    return httpx.Client(
        base_url="http://testserver", transport=httpx.MockTransport(handler)
    )


def test_attaches_bearer_header_on_every_request() -> None:
    seen: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization", "")
        return httpx.Response(200, json={"ok": True})

    with mock_client(handler) as http:
        assert Client("http://testserver", TOKEN, http=http).get("/x") == {
            "ok": True
        }
    assert seen["auth"] == f"Bearer {TOKEN}"


@pytest.mark.parametrize(
    ("status", "error"),
    [(401, Unauthorized), (403, Forbidden), (404, NotFound)],
)
def test_status_maps_to_typed_error(status: int, error: type) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"error": {"code": "x", "message": "x", "details": None}}
        return httpx.Response(status, json=body)

    with mock_client(handler) as http, pytest.raises(error):
        Client("http://testserver", TOKEN, http=http).get("/x")


def test_other_status_surfaces_server_detail() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            409,
            json={
                "error": {
                    "code": "conflict",
                    "message": "already exists: webphone",
                    "details": None,
                }
            },
        )

    with mock_client(handler) as http, pytest.raises(RequestFailed) as caught:
        Client("http://testserver", TOKEN, http=http).post("/sources", {})
    assert caught.value.status_code == 409
    assert message(caught.value) == "already exists: webphone"


def test_connection_failure_maps_to_unreachable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with mock_client(handler) as http, pytest.raises(Unreachable) as caught:
        Client("http://testserver", TOKEN, http=http).get("/health")
    assert "testserver" in message(caught.value)
    assert TOKEN not in message(caught.value)


def test_no_current_context_raises_no_context(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HRONO_HOME", str(tmp_path))
    with pytest.raises(NoContext):
        from_context()
    assert "hrono context add" in message(NoContext())


def test_token_never_appears_in_a_message() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = {"error": {"code": "unauthorized", "message": "nope"}}
        return httpx.Response(401, json=body)

    with mock_client(handler) as http:
        try:
            Client("http://testserver", TOKEN, http=http).get("/users")
        except Unauthorized as exc:
            assert TOKEN not in message(exc)
            assert TOKEN not in str(exc)


def test_live_round_trip_against_a_real_app() -> None:
    app = create_app(master_key=Fernet.generate_key())
    client = Client("http://testserver", TOKEN, http=TestClient(app))
    assert client.get("/health") == {"status": "ok"}
    assert client.get("/version")["name"] == "hrono"
