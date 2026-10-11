import sqlite3
import threading
from collections.abc import Iterator
from importlib.metadata import version
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.db.database import Database
from hrono.server.app import create_app

KEY = Fernet.generate_key()


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(db_path=tmp_path / "hrono.db", master_key=KEY)
    with TestClient(app) as running:
        yield running


def test_health_reports_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": {"ok": True, "in_transaction": False},
        "worker": "alive",
    }


def test_the_bare_address_opens_the_dashboard(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/ui"


def test_health_is_degraded_when_the_database_is_unusable(
    client: TestClient,
) -> None:
    dead = sqlite3.connect(":memory:")
    dead.close()
    client.app.state.db = Database.adopt(dead)  # type: ignore[attr-defined]
    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["database"]["ok"] is False


def test_health_is_degraded_when_the_worker_is_dead(
    client: TestClient,
) -> None:
    worker = client.app.state.worker  # type: ignore[attr-defined]
    worker.stop()
    worker.join(timeout=5)
    response = client.get("/health")
    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "database": {"ok": True, "in_transaction": False},
        "worker": "dead",
    }


def test_version_reports_installed_package_version(client: TestClient) -> None:
    response = client.get("/version")
    assert response.status_code == 200
    assert response.json() == {"name": "hrono", "version": version("hrono")}


def test_health_is_degraded_when_only_the_reclaimer_is_dead(
    client: TestClient,
) -> None:
    # the supervisor still runs, so `is_alive()` says alive; the thread
    # that requeues stranded jobs is gone, and /health must not paper over it.
    worker = client.app.state.worker  # type: ignore[attr-defined]
    worker._beat_thread = threading.Thread(target=lambda: None)

    response = client.get("/health")

    assert response.status_code == 503
    assert response.json()["worker"] == "dead"
    assert worker.is_alive()  # the supervisor never stopped
