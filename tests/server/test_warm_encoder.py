"""#168: the server pays for the model's weights, not the first question.

Measured before this: recall #1 13.3s, #2 14ms — the whole cost landing on one
arbitrary user. The warm-up moves it off the request path, and the only way to
know it really did is to watch a REAL model arrive in the cache, so this is
guarded by the same env var as the runner's real-backend test rather than
skipped outright (#108).
"""

from __future__ import annotations

import json
import logging
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

_NEEDS_WEIGHTS = pytest.mark.skipif(
    not os.environ.get("HRONO_TEST_REAL_MODEL"),
    reason="set HRONO_TEST_REAL_MODEL=<id> to load real weights",
)


@_NEEDS_WEIGHTS
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


def test_a_server_with_no_embedding_model_starts_and_says_why_quietly(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A first boot with nothing registered is ordinary, and must stay quiet.

    NOT guarded by the env var: this registers no model, so it needs no
    weights, no network and no cache, and it is the guard that must run
    everywhere (qa, 2026-09-25).

    The assertion is on the LOG, not on the server surviving. The warm-up runs
    in a daemon thread, so a raise there could never take the server down and
    "it still starts" would pass with the error handling deleted -- it did,
    when this test was first written. What the try/except actually buys is
    that the failure is a debug line instead of a traceback on the operator's
    stderr at every boot, so that is what is measured here.
    """
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)

    with caplog.at_level(logging.DEBUG, logger="hrono"):
        app = create_app(connection=conn, master_key=KEY, key_id=1)
        with TestClient(app):
            deadline = time.monotonic() + 10
            while not _warned(caplog):
                if time.monotonic() > deadline:
                    pytest.fail("the warm-up neither warmed nor reported")
                time.sleep(0.05)

    assert _warned(caplog)
    conn.close()


def _warned(caplog: pytest.LogCaptureFixture) -> bool:
    return any(
        "query encoder not warmed" in record.message
        for record in caplog.records
    )
