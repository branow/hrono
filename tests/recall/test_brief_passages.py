"""T25.3: a written brief lands in the passage store as node:// passages."""

import json
from collections.abc import Iterator

import pytest

from hrono.cluster import store as cluster_store
from hrono.cluster.blend import register_path_bodies
from hrono.db.database import Database, open_database
from hrono.embed.op import embed
from hrono.embed.store import get_vector
from hrono.ingest import store as istore
from hrono.ingest.identity import Address, content_hash
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.recall import fts
from hrono.recall.brief_passages import store_brief
from hrono.registry import store as registry_store
from hrono.summarize import store as condensations

BRIEF = "# Authentication\n\nThe login flow issues bearer tokens per request.\n"


def register_model(conn: object) -> None:
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "models",
        "emb",
        json.dumps(
            {
                "name": "emb",
                "kind": "embedding",
                "connection": None,
                "model": "fake",
                "params": {"dims": 4, "batch_size": 8},
            }
        ),
        None,
        "t",
    )


def fake_encoder(model_id: str):
    def encode(texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0, 0.0, 0.0] for _ in texts]

    return encode


def embed_job() -> Job:
    return Job(
        id="e",
        parent_id=None,
        tree=None,
        op="embed",
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database(open_database(tmp_path / "hrono.db"))  # type: ignore[operator]
    with database.connect() as conn, conn:
        register_model(conn)
    yield database
    database.close()


def _node_passages(db: Database) -> list:
    with db.connect() as conn:
        return conn.execute(
            "SELECT uri, source, version, content_hash FROM passages "
            "WHERE source_type = 'node' ORDER BY ordinal"
        ).fetchall()


def test_brief_is_stored_as_node_passages(db: Database) -> None:
    with db.connect() as conn, conn:
        store_brief(conn, 5, BRIEF, "sig-abc")
    rows = _node_passages(db)
    assert rows
    for row in rows:
        assert row["uri"].startswith("node://hrono/nodes/5/authentication@")
        assert row["version"] == "sig-abc"
        assert row["source"] == "node-5"  # origin tag = source_type 'node'


def test_brief_passages_are_embeddable_and_fts_indexed(db: Database) -> None:
    with db.connect() as conn, conn:
        store_brief(conn, 5, BRIEF, "sig-abc")
    embed(embed_job(), JobContext(db), encoder_for=fake_encoder)
    with db.connect() as conn:
        for row in _node_passages(db):
            assert get_vector(conn, row["content_hash"], "emb") is not None
        assert fts.search(conn, "bearer OR tokens")  # keyword-indexed too


def test_signature_change_replaces_the_nodes_brief_passages(
    db: Database,
) -> None:
    with db.connect() as conn, conn:
        store_brief(conn, 5, BRIEF, "sig-old")
    with db.connect() as conn, conn:
        store_brief(
            conn, 5, "# Authentication\n\nNow uses sessions.\n", "sig-new"
        )
    with db.connect() as conn:
        versions = {r["version"] for r in _node_passages(db)}
    assert versions == {"sig-new"}  # old-signature passages replaced


def test_node_sections_are_excluded_from_clustering_and_condensing(
    db: Database,
) -> None:
    body = b"def real(): return 1\n"
    with db.connect() as conn, conn:
        # a real source section (git) + its content/path vectors
        istore.upsert_content(conn, content_hash(body), body)
        register_path_bodies(
            conn, ["a.py"]
        )  # so the git combined vector exists
        section_id = istore.insert_section(
            conn,
            source="repo",
            address=Address("git", "ex/repo", "a.py", "v1"),
            start=0,
            end=len(body),
            content_hash=content_hash(body),
            ordinal=0,
        )
        store_brief(conn, 5, BRIEF, "sig-abc")  # a node brief section too
    with db.connect() as conn:
        # condense only sees the git section, never the node brief section
        pending = {h for h, _ in condensations.pending(conn, "emb")}
        assert content_hash(body) in pending
        node_hashes = {r["content_hash"] for r in _node_passages(db)}
        assert not (pending & node_hashes)
        # cluster only sees the git section id
        embed(embed_job(), JobContext(db), encoder_for=fake_encoder)
    with db.connect() as conn:
        ids = {
            sid
            for sid, _ in cluster_store.section_combined_vectors(conn, "emb")
        }
    assert ids == {section_id}
