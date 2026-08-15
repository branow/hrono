from importlib.metadata import version

from fastapi.testclient import TestClient

from hrono.server.app import create_app


def client() -> TestClient:
    return TestClient(create_app())


def test_health_reports_ok() -> None:
    response = client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_reports_installed_package_version() -> None:
    response = client().get("/version")
    assert response.status_code == 200
    assert response.json() == {"name": "hrono", "version": version("hrono")}


def test_liveness_routes_need_no_authorization_header() -> None:
    reachable = client()
    assert "authorization" not in {key.lower() for key in reachable.headers}
    assert reachable.get("/health").status_code == 200
    assert reachable.get("/version").status_code == 200


def test_unknown_route_is_not_found() -> None:
    assert client().get("/nope").status_code == 404
