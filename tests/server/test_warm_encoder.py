"""#168: the server pays for the model's weights, not the first question.

Measured before this: recall #1 13.3s, #2 14ms — the whole cost landing on one
arbitrary user. The warm-up moves it off the request path, and the only way to
know it really did is to watch a REAL model arrive in the cache, so this is
guarded by the same env var as the runner's real-backend test rather than
skipped outright (#108).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.embed import runner
from hrono.registry import store as registry_store
from hrono.server.app import create_app

KEY = Fernet.generate_key()

pytestmark = pytest.mark.skipif(
    not os.environ.get("HRONO_TEST_REAL_MODEL"),
    reason="set HRONO_TEST_REAL_MODEL=<id> to load real weights",
)


def test_starting_the_server_warms_the_query_encoder(tmp_path: Path) -> None:
    model_id = os.environ["HRONO_TEST_REAL_MODEL"]
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    registry_store.insert(
        conn,
        "models",
        "emb",
        json.dumps(
            {
                "name": "emb",
                "kind": "embedding",
                "connection": None,
                "model": model_id,
                "params": {"dims": 384},
            }
        ),
        None,
        "t",
    )
    runner._CACHE.clear()

    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app):
        deadline = time.monotonic() + 120
        while model_id not in runner._CACHE:
            if time.monotonic() > deadline:
                pytest.fail("the server never warmed the query encoder")
            time.sleep(0.2)

    assert model_id in runner._CACHE
    conn.close()


def test_a_server_with_no_embedding_model_still_starts(tmp_path: Path) -> None:
    # the warm-up must never be fatal: a database with nothing registered yet
    # is a perfectly ordinary first boot.
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)

    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        assert client.get("/health").status_code in (200, 401, 403)

    conn.close()
