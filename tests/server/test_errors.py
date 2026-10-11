import logging

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hrono.errors import (
    AppError,
    BadRequest,
    Conflict,
    Forbidden,
    Invalid,
    NotFound,
    Unauthorized,
)
from hrono.server.errors import install


class Teapot(AppError):
    status_code = 418
    code = "teapot"


def app_with_demo_routes() -> FastAPI:
    app = FastAPI()
    install(app)

    @app.get("/raise/{code}")
    def raise_error(code: str) -> None:
        errors = {
            "bad": BadRequest("bad input"),
            "unauth": Unauthorized("no token"),
            "forbidden": Forbidden("denied"),
            "notfound": NotFound("missing", details={"name": "x"}),
            "conflict": Conflict("exists"),
            "invalid": Invalid("bad field"),
            "teapot": Teapot("short and stout"),
        }
        raise errors[code]

    @app.get("/boom")
    def boom() -> None:
        raise ValueError("secret-internal-detail")

    return app


@pytest.mark.parametrize(
    ("path", "status", "code"),
    [
        ("bad", 400, "bad-request"),
        ("unauth", 401, "unauthorized"),
        ("forbidden", 403, "forbidden"),
        ("notfound", 404, "not-found"),
        ("conflict", 409, "conflict"),
        ("invalid", 422, "validation-error"),
    ],
)
def test_each_subclass_maps_to_its_envelope(
    path: str, status: int, code: str
) -> None:
    client = TestClient(app_with_demo_routes())
    response = client.get(f"/raise/{path}")
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "details"}
    assert body["error"]["code"] == code


def test_unauthorized_carries_the_www_authenticate_header() -> None:
    client = TestClient(app_with_demo_routes())
    response = client.get("/raise/unauth")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_details_are_carried_through() -> None:
    client = TestClient(app_with_demo_routes())
    body = client.get("/raise/notfound").json()
    assert body["error"]["details"] == {"name": "x"}


def test_a_new_subclass_needs_no_handler_change() -> None:
    client = TestClient(app_with_demo_routes())
    response = client.get("/raise/teapot")
    assert response.status_code == 418
    assert response.json()["error"]["code"] == "teapot"


def test_uncaught_exception_is_a_safe_500(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = TestClient(app_with_demo_routes(), raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="hrono"):
        response = client.get("/boom")
    assert response.status_code == 500
    body = response.json()
    assert body == {
        "error": {
            "code": "internal-error",
            "message": "internal error",
            "details": None,
        }
    }
    assert "secret-internal-detail" not in response.text
    assert any(record.exc_info is not None for record in caplog.records)


def test_4xx_logs_warning_5xx_logs_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = TestClient(app_with_demo_routes(), raise_server_exceptions=False)
    with caplog.at_level(logging.WARNING, logger="hrono"):
        client.get("/raise/notfound")
    assert any(r.levelno == logging.WARNING for r in caplog.records)
