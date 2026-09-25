"""#161: a domain failure reaches the client with the name #145 gave it.

Only `AppError` was registered on the boundary, so every `DomainError` fell
into the catch-all and rendered `internal-error` — the operator whose server
had no embedding model was told "internal error" while the log underneath said
"no embedding model available".
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster import ClusterError, TooFewPoints
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.embed.runner import EmbedError
from hrono.errors import Invalid
from hrono.ingest import SyncError
from hrono.server.app import create_app
from hrono.server.errors import install

KEY = Fernet.generate_key()


@pytest.fixture
def raising() -> Iterator[TestClient]:
    """A bare app carrying only the error handlers, plus routes that raise."""
    app = FastAPI()
    install(app)

    @app.get("/embed")
    def _embed() -> None:
        raise EmbedError("no embedding model available")

    @app.get("/cluster")
    def _cluster() -> None:
        raise TooFewPoints("too few vectors to cluster: 3 < 12")

    @app.get("/sync")
    def _sync() -> None:
        raise SyncError("the source could not be read")

    @app.get("/invalid")
    def _invalid() -> None:
        raise Invalid("that will not do")

    @app.get("/foreign")
    def _foreign() -> None:
        raise RuntimeError("sqlite says something about its internals")

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


@pytest.mark.parametrize(
    ("path", "code", "fragment"),
    [
        ("/embed", "embed-error", "no embedding model available"),
        ("/cluster", "too-few-points", "too few vectors"),
        ("/sync", "sync-error", "could not be read"),
    ],
)
def test_a_domain_failure_keeps_its_code_and_its_message(
    raising: TestClient, path: str, code: str, fragment: str
) -> None:
    response = raising.get(path)

    assert response.status_code == 500  # #145 ruled: these stay 500
    body = response.json()["error"]
    assert body["code"] == code
    assert fragment in body["message"]


def test_a_subclass_answers_with_its_own_code_not_its_family_s(
    raising: TestClient,
) -> None:
    """`TooFewPoints` is a `ClusterError` and does NOT answer as one.

    I expected the family's code here and was wrong, which is worth keeping as
    a test rather than a correction: #145's rule is that each class declares
    its own, and `TooFewPoints` declares one deliberately because it is the one
    clustering failure that is not a failure — a caller may answer it by
    COLLECTING (#094, #112). A client that could not tell it from a broken
    clusterer would have to guess at exactly the distinction the type exists
    to make.
    """
    assert issubclass(TooFewPoints, ClusterError)
    assert ClusterError.code == "cluster-error"

    assert raising.get("/cluster").json()["error"]["code"] == "too-few-points"


def test_an_app_error_is_untouched(raising: TestClient) -> None:
    # the existing path must not change: Invalid is a 422 with its own code.
    response = raising.get("/invalid")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation-error"


def test_a_foreign_exception_still_says_nothing(raising: TestClient) -> None:
    # the whole point of the catch-all: another library's wording must never
    # become hrono's answer. It reaches the log, not the client.
    response = raising.get("/foreign")

    body = response.json()["error"]
    assert response.status_code == 500
    assert body["code"] == "internal-error"
    assert body["message"] == "internal error"
    assert "sqlite" not in str(body)


def test_the_real_server_names_a_missing_embedding_model(
    tmp_path: Path,
) -> None:
    """The case from the ticket, through the real app and a real route.

    `POST /trees/<t>/nodes/<id>/dissolve` resolves an embedding model, and a
    server with none registered raised `EmbedError` into the catch-all.
    """
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    token = create_user(conn, "admin", "admin")[1]
    with conn:
        conn.execute(
            "INSERT INTO nodes(tree, level, label, created_at) "
            "VALUES ('default', 0, 0, 't')"
        )
        node = int(conn.execute("SELECT MAX(id) FROM nodes").fetchone()[0])
    app = create_app(connection=conn, master_key=KEY, key_id=1)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.post(
            f"/trees/default/nodes/{node}/dissolve",
            headers={"Authorization": f"Bearer {token}"},
        )

    body = response.json()["error"]
    assert body["code"] == "embed-error"
    assert "embedding model" in body["message"]
    conn.close()
