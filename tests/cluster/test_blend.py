import json
import math
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from hrono.cluster.blend import (
    FOLDER_DIMS,
    FOLDER_WEIGHT,
    TEXT_WEIGHT,
    clustering_vector,
    combined_vector,
    folder_vector,
    path_body,
    register_path_bodies,
)
from hrono.db.database import Database
from hrono.embed import store as vstore
from hrono.embed.op import embed
from hrono.ingest import store as istore
from hrono.ingest.identity import content_hash
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.registry import store as registry_store


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _unit(vec: Sequence[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec]


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    yield database
    database.close()


def _fake_encoder(dims: int):
    def build(model_id: str):
        def encode(texts: list[str]) -> list[list[float]]:
            return [[float(len(t) % 5) + 1.0] * dims for t in texts]

        return encode

    return build


def _register_model(conn: object, name: str = "emb", dims: int = 4) -> None:
    body = {
        "name": name,
        "kind": "embedding",
        "connection": None,
        "model": "fake/model",
        "params": {"dims": dims, "batch_size": 2},
    }
    registry_store.insert(conn, "models", name, json.dumps(body), None, "t")


def _job() -> Job:
    return Job(
        id="j",
        parent_id=None,
        tree=None,
        op="embed",
        scope={"type": "model", "name": "emb"},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


def test_a_repeated_path_registers_one_body(db: Database) -> None:
    with db.connect() as conn, conn:
        register_path_bodies(conn, ["src/a.py", "src/a.py", "src/b.py"])
    with db.connect() as conn:
        assert istore.content_count(conn) == 2  # two distinct paths


def test_path_embeds_once_with_the_content_model(db: Database) -> None:
    body = b"class A: pass\n"
    path = "src/a.py"
    with db.connect() as conn, conn:
        istore.upsert_content(conn, content_hash(body), body)
        register_path_bodies(conn, [path])
        _register_model(conn)
    embed(_job(), JobContext(db), encoder_for=_fake_encoder(4))
    embed(_job(), JobContext(db), encoder_for=_fake_encoder(4))  # re-run
    with db.connect() as conn:
        path_vector = vstore.get_vector(
            conn, content_hash(path_body(path)), "emb"
        )
        assert path_vector is not None and len(path_vector) == 4
        # body + path each embedded exactly once
        assert vstore.vector_count(conn, "emb") == 2


def test_combined_vector_blends_stored_components(db: Database) -> None:
    body = b"def f():\n    return 1\n"
    path = "src/f.py"
    with db.connect() as conn, conn:
        istore.upsert_content(conn, content_hash(body), body)
        register_path_bodies(conn, [path])
        _register_model(conn)
    embed(_job(), JobContext(db), encoder_for=_fake_encoder(4))
    with db.connect() as conn:
        combined = combined_vector(conn, content_hash(body), path, "emb")
    assert combined is not None
    assert len(combined) == 4 + FOLDER_DIMS  # text ++ hashed folders


def test_combined_vector_is_none_when_a_component_is_missing(
    db: Database,
) -> None:
    body = b"x = 1\n"
    with db.connect() as conn, conn:
        istore.upsert_content(conn, content_hash(body), body)
        _register_model(conn)
    # nothing embedded yet -> content vector missing
    with db.connect() as conn:
        assert combined_vector(conn, content_hash(body), "p.py", "emb") is None


def test_clustering_weighs_text_and_folders_by_the_baked_weights() -> None:
    t1, t2 = _unit([1, 2, 3, 4]), _unit([4, 3, 2, 1])
    f1 = folder_vector("lear", "queue_services/entity-pay/worker.py")
    f2 = folder_vector("lear", "queue_services/entity-filer/worker.py")
    left = _dot(clustering_vector(t1, f1), clustering_vector(t2, f2))
    right = TEXT_WEIGHT * _dot(t1, t2) + FOLDER_WEIGHT * _dot(f1, f2)
    assert left == pytest.approx(right)


def test_shared_leading_folders_weigh_by_one_over_their_depth() -> None:
    # depths 1-4 shared of 5 and 5: sum 1/d over shared over the total
    a = folder_vector("lear", "queue_services/entity-pay/src/worker.py")
    b = folder_vector("lear", "queue_services/entity-pay/src/config.py")
    shared = 1 + 1 / 2 + 1 / 3 + 1 / 4
    total = shared + 1 / 5
    assert _dot(a, b) == pytest.approx(shared / total, abs=0.02)


def test_the_source_is_the_heaviest_folder() -> None:
    here = folder_vector("lear", "legal-api/models/filing.py")
    same_repo = folder_vector("lear", "colin-api/models/filing.py")
    other_repo = folder_vector("sbc-pay", "legal-api/models/filing.py")
    assert _dot(here, same_repo) > 0.3
    assert abs(_dot(here, other_repo)) < 0.05  # every prefix differs


def test_a_condensed_section_is_read_by_its_condensation(
    db: Database,
) -> None:
    body = b"# MIT licence\nimport os\ndef pay(): ...\n"
    condensed = "Applies a confirmed payment to its filing."
    with db.connect() as conn, conn:
        istore.upsert_content(conn, content_hash(body), body)
        _register_model(conn)
        registry_store.insert(
            conn,
            "models",
            "condense",
            json.dumps(
                {
                    "name": "condense",
                    "kind": "text",
                    "model": "m",
                    "role": "condense",
                }
            ),
            None,
            "t",
        )
        conn.execute(
            "INSERT INTO condensations(content_hash, model_name, text, "
            "input_tokens, output_tokens, created_at) "
            "VALUES (?, 'condense', ?, 1, 1, 'now')",
            (content_hash(body), condensed),
        )
        istore.upsert_content(
            conn, content_hash(condensed.encode()), condensed.encode()
        )
    embed(_job(), JobContext(db), encoder_for=_fake_encoder(4))
    with db.connect() as conn:
        combined = combined_vector(conn, content_hash(body), "pay.py", "emb")
        text = vstore.get_vector(conn, content_hash(condensed.encode()), "emb")
    assert combined is not None and text is not None
    assert combined[:4] == pytest.approx(
        [math.sqrt(TEXT_WEIGHT) * x for x in _unit(text)]
    )
