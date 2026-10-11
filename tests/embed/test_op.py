import json
import time
from collections.abc import Iterator

import pytest

from hrono.db.database import Database
from hrono.embed import store as vstore
from hrono.embed.op import embed
from hrono.embed.runner import EmbedError
from hrono.ingest import store as istore
from hrono.ingest.identity import content_hash
from hrono.jobs import store as jobs_store
from hrono.jobs.model import Job, serialize_scope
from hrono.jobs.ops import JobContext
from hrono.jobs.worker import Worker
from hrono.registry import store as registry_store

BODIES = [b"class A: pass\n", b"def f():\n    return 1\n", b"x = 42\n"]


def fake_encoder(dims: int):
    def build(model_id: str):
        def encode(texts: list[str]) -> list[list[float]]:
            return [[float(len(t) % 7)] * dims for t in texts]

        return encode

    return build


def register_model(
    conn: object, name: str, dims: int | None = 4, model: str = "fake/model"
) -> None:
    params: dict[str, object] = {"batch_size": 2}
    if dims is not None:
        params["dims"] = dims
    body = {
        "name": name,
        "kind": "embedding",
        "connection": None,
        "model": model,
        "params": params,
    }
    registry_store.insert(conn, "models", name, json.dumps(body), None, "t")


def job(model: str, job_id: str = "j") -> Job:
    return Job(
        id=job_id,
        parent_id=None,
        tree=None,
        op="embed",
        scope={"type": "model", "name": model},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def db(tmp_path: object) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        for body in BODIES:
            istore.upsert_content(conn, content_hash(body), body)
        register_model(conn, "emb")
    yield database
    database.close()


def test_embeds_every_missing_hash_with_the_declared_dims(db: Database) -> None:
    embed(job("emb"), JobContext(db), encoder_for=fake_encoder(4))
    with db.connect() as conn:
        assert vstore.vector_count(conn, "emb") == len(BODIES)
        vector = vstore.get_vector(conn, content_hash(BODIES[0]), "emb")
        assert vector is not None
        assert len(vector) == 4


def test_re_embed_is_idempotent(db: Database) -> None:
    embed(job("emb"), JobContext(db), encoder_for=fake_encoder(4))
    embed(job("emb"), JobContext(db), encoder_for=fake_encoder(4))
    with db.connect() as conn:
        assert vstore.vector_count(conn, "emb") == len(BODIES)


def test_shared_content_is_embedded_once(db: Database) -> None:
    # a body identical to an existing one adds no new content row, so no new
    # vector beyond the distinct hashes.
    with db.connect() as conn, conn:
        istore.upsert_content(conn, content_hash(BODIES[0]), BODIES[0])
    embed(job("emb"), JobContext(db), encoder_for=fake_encoder(4))
    with db.connect() as conn:
        assert vstore.vector_count(conn, "emb") == len(BODIES)


def test_model_swap_re_embeds_under_a_new_key(db: Database) -> None:
    embed(job("emb"), JobContext(db), encoder_for=fake_encoder(4))
    with db.connect() as conn, conn:
        register_model(conn, "emb2", dims=8, model="other/model")
    embed(job("emb2"), JobContext(db), encoder_for=fake_encoder(8))
    with db.connect() as conn:
        assert vstore.vector_count(conn, "emb") == len(BODIES)
        assert vstore.vector_count(conn, "emb2") == len(BODIES)
        original = vstore.get_vector(conn, content_hash(BODIES[0]), "emb")
        swapped = vstore.get_vector(conn, content_hash(BODIES[0]), "emb2")
        assert original is not None and len(original) == 4
        assert swapped is not None and len(swapped) == 8


def test_dims_mismatch_is_rejected(db: Database) -> None:
    # model declares dims 4 but the encoder emits dim 3
    with pytest.raises(EmbedError, match="dims mismatch"):
        embed(job("emb"), JobContext(db), encoder_for=fake_encoder(3))


def test_no_embedding_model_raises(db: Database) -> None:
    with db.connect() as conn, conn:
        conn.execute("DELETE FROM registry WHERE collection = 'models'")
    with pytest.raises(EmbedError, match="no embedding model"):
        embed(job("emb"), JobContext(db), encoder_for=fake_encoder(4))


def test_embed_runs_as_a_job_and_failure_is_isolated(
    db: Database, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("hrono.embed.op._default_encoder_for", fake_encoder(4))
    worker = Worker(db)
    worker.start()
    try:
        with db.connect() as conn:
            jobs_store.insert(
                conn,
                "e1",
                None,
                None,
                "embed",
                serialize_scope({"type": "model", "name": "emb"}),
                "t",
            )
        deadline = time.monotonic() + 5.0
        row = None
        while time.monotonic() < deadline:
            with db.connect() as conn:
                row = jobs_store.get(conn, "e1")
            if row is not None and row["status"] in ("succeeded", "failed"):
                break
            time.sleep(0.01)
    finally:
        worker.stop()
        worker.join(timeout=5)
    assert row is not None
    assert row["status"] == "succeeded"
    with db.connect() as conn:
        assert vstore.vector_count(conn, "emb") == len(BODIES)


def test_embed_of_a_scoped_tree_skips_other_trees_content(
    db: Database, tmp_path: object
) -> None:
    """A tree's embed stage must not vectorise another tree's corpus.

    ``missing`` selected every content row with no vector, so tree A's embed
    paid for tree B's backlog (and for orphan rows nothing references). The
    scope is everything A's pipeline reads vectors for: its sections and
    passages, their paths, its briefs.
    """
    import json as _json

    from hrono.ingest import store as istore
    from hrono.ingest.identity import Address
    from hrono.registry import store as registry_store

    mine = b"content that belongs to the scoped tree"
    foreign = b"content that belongs to someone else"
    with db.connect() as conn, conn:
        for body, source in ((mine, "mine-src"), (foreign, "other-src")):
            istore.upsert_content(conn, content_hash(body), body)
            istore.insert_section(
                conn,
                source=source,
                address=Address("git", "x", f"{source}/f.py", "v"),
                start=0,
                end=len(body),
                content_hash=content_hash(body),
                ordinal=0,
            )
        registry_store.insert(
            conn,
            "trees",
            "scoped",
            _json.dumps({"name": "scoped", "sources": ["mine-src"]}),
            None,
            "t",
        )
    scoped = Job(
        id="e-scoped",
        parent_id=None,
        tree="scoped",
        op="embed",
        scope={"type": "model", "name": "emb"},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )

    embed(scoped, JobContext(db), encoder_for=fake_encoder(4))

    with db.connect() as conn:
        assert vstore.get_vector(conn, content_hash(mine), "emb") is not None
        assert vstore.get_vector(conn, content_hash(foreign), "emb") is None
