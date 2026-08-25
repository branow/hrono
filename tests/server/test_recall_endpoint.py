"""T28: the synchronous recall endpoint — role, shape, explore message."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.cluster.blend import path_body, register_path_bodies
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.embed.store import upsert_vector
from hrono.ingest.identity import Address, content_hash
from hrono.ingest.store import insert_section, upsert_content
from hrono.registry import store as registry_store
from hrono.server.app import create_app

KEY = Fernet.generate_key()
DIMS = 8
PATH = "src/x.py"


def unit(index: int) -> list[float]:
    vec = [0.0] * DIMS
    vec[index] = 1.0
    return vec


def add_passage(conn: object, body: bytes, vec: list[float]) -> None:
    digest = content_hash(body)
    upsert_content(conn, digest, body)  # type: ignore[arg-type]
    upsert_vector(conn, digest, "emb", vec)  # type: ignore[arg-type]
    section_id = insert_section(
        conn,  # type: ignore[arg-type]
        source="repo",
        address=Address("git", "ex/repo", PATH, "v1"),
        start=0,
        end=len(body),
        content_hash=digest,
        ordinal=0,
    )
    conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO passages(section_id, source, source_type, instance, path, "
        "version, uri, byte_start, byte_end, content_hash, sp_paths, ordinal, "
        "created_at) VALUES (?, 'repo', 'git', 'ex/repo', ?, 'v1', ?, 0, ?, ?, "
        "'[]', 0, 't')",
        (section_id, PATH, f"git://ex/repo/{PATH}@v1", len(body), digest),
    )


class Harness:
    def __init__(self, client: TestClient, tokens: dict[str, str]) -> None:
        self.client = client
        self.tokens = tokens

    def auth(self, role: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.tokens[role]}"}


@pytest.fixture
def harness(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Harness]:
    conn = open_database(tmp_path / "hrono.db")
    reconcile(conn, KEY)
    tokens = {
        role: create_user(conn, role, role)[1]
        for role in ("reader", "writer", "admin")
    }
    registry_store.insert(
        conn,
        "models",
        "emb",
        json.dumps(
            {
                "name": "emb",
                "kind": "embedding",
                "connection": None,
                "model": "fake",
                "params": {"dims": DIMS},
            }
        ),
        None,
        "t",
    )
    register_path_bodies(conn, [PATH])
    upsert_vector(conn, content_hash(path_body(PATH)), "emb", unit(2))
    add_passage(
        conn, b"the authentication flow issues bearer tokens\n", unit(0)
    )
    for i in range(15):
        add_passage(conn, f"unrelated topic {i}\n".encode(), unit(1))
    conn.commit()
    # the endpoint embeds the query via _query_encode -> fake it (e0 = answer)
    monkeypatch.setattr(
        "hrono.server.trees._query_encode",
        lambda model_id: lambda texts: [unit(0) for _ in texts],
    )
    app = create_app(connection=conn, master_key=KEY, key_id=1)
    with TestClient(app) as client:
        yield Harness(client, tokens)
    conn.close()


def test_unauthenticated_is_rejected(harness: Harness) -> None:
    resp = harness.client.post(
        "/trees/default/recall", json={"question": "auth?"}
    )
    assert resp.status_code == 401


def test_reader_can_recall_and_gets_ranked_hits(harness: Harness) -> None:
    resp = harness.client.post(
        "/trees/default/recall",
        json={"question": "authentication?"},
        headers=harness.auth("reader"),
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["message"] is None
    assert payload["hits"]
    hit = payload["hits"][0]
    assert set(hit) == {"uri", "kind", "header", "body", "score"}
    assert hit["kind"] == "source"
    assert "bearer tokens" in hit["body"]


def test_no_answer_returns_the_explore_message(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    # re-point the query encoder at an orthogonal vector -> no confident hit
    monkeypatch.setattr(
        "hrono.server.trees._query_encode",
        lambda model_id: lambda texts: [unit(3) for _ in texts],
    )
    resp = harness.client.post(
        "/trees/default/recall",
        json={"question": "unrelated?"},
        headers=harness.auth("reader"),
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["hits"] == []
    assert payload["message"] == "no confident matches - explore the map."
