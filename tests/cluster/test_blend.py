import json
import math
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest

from hrono.cluster.blend import (
    ALPHA,
    combine,
    combined_vector,
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


def test_alpha_is_the_baked_half() -> None:
    assert ALPHA == 0.5


def test_blend_identity_holds_for_unit_vectors() -> None:
    c1, c2 = _unit([1, 2, 3, 4]), _unit([4, 3, 2, 1])
    p1, p2 = _unit([0, 1, 0, 1]), _unit([1, 0, 1, 0])
    left = _dot(combine(c1, p1), combine(c2, p2))
    right = (1 - ALPHA) * _dot(c1, c2) + ALPHA * _dot(p1, p2)
    assert left == pytest.approx(right)


def test_combined_has_double_the_dims_and_is_deterministic() -> None:
    content = _unit([1, 1, 1, 1, 1])
    path = _unit([1, 0, 0, 0, 0])
    combined = combine(content, path)
    assert len(combined) == 2 * len(content)
    assert combined == combine(content, path)


def test_non_unit_inputs_are_normalised_so_the_identity_holds() -> None:
    c1, c2 = [2, 4, 6, 8], [8, 6, 4, 2]  # non-unit
    p1, p2 = [0, 3, 0, 3], [3, 0, 3, 0]
    left = _dot(combine(c1, p1), combine(c2, p2))
    right = (1 - ALPHA) * _dot(_unit(c1), _unit(c2)) + ALPHA * _dot(
        _unit(p1), _unit(p2)
    )
    assert left == pytest.approx(right)


def test_zero_vector_does_not_divide_by_zero() -> None:
    combined = combine([0.0, 0.0], [1.0, 0.0])
    assert len(combined) == 4
    assert combined[0] == 0.0 and combined[1] == 0.0


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
    assert len(combined) == 8


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
