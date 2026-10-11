"""Every stored passage is embeddable + path-blended by the existing ops.

Passages carry a content hash and share their file's path, and split stores each
passage body as a ``contents`` row (like sections), so the embed op (which
embeds every content) already vectorises passage bodies, and the build's
``register_path_bodies`` already embeds their path. These tests lock that in: a
future change that stops indexing passages must fail here. No new production
code is needed — this confirms the property over sync -> split -> embed.
"""

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from hrono.cluster.blend import combine, combined_vector, path_body
from hrono.db.database import Database
from hrono.embed.op import embed
from hrono.embed.store import get_vector, vector_count
from hrono.ingest.identity import content_hash
from hrono.ingest.split_op import split_source
from hrono.ingest.sync import sync
from hrono.jobs.model import Job
from hrono.registry import store as registry_store
from tests.context import job_context
from tests.repo_template import memoized

DIMS = 4


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True
    )


@memoized
def make_repo(path: Path) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True)
    _git(path, "config", "user.email", "t@example.com")
    _git(path, "config", "user.name", "Test")
    (path / "doc.md").write_text(
        "# Title\n\n" + ("prose paragraph here. " * 40)
    )
    (path / "tiny.txt").write_text("one small line\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-qm", "first")
    return path.as_uri()


def fake_encoder(model_id: str):
    def encode(texts: list[str]) -> list[list[float]]:
        return [[float(len(t) % 5 + 1), 1.0, 2.0, 0.5] for t in texts]

    return encode


def register_source(conn: object, url: str) -> None:
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "sources",
        "repo",
        json.dumps({"name": "repo", "type": "git", "url": url, "auth": {}}),
        None,
        "t",
    )


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
                "params": {"dims": DIMS, "batch_size": 8},
            }
        ),
        None,
        "t",
    )


def _job(op: str) -> Job:
    return Job(
        id="j",
        parent_id=None,
        tree=None,
        op=op,
        scope={"type": "source", "name": "repo"}
        if op in ("sync", "split")
        else {},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Database]:
    monkeypatch.chdir(tmp_path)
    url = make_repo(tmp_path / "remote")
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn:
        register_source(conn, url)
        register_model(conn)
    sync(_job("sync"), job_context(database, tmp_path))
    split_source(_job("split"), job_context(database, tmp_path))
    embed(
        _job("embed"), job_context(database, tmp_path), encoder_for=fake_encoder
    )
    yield database
    database.close()


def _passages(db: Database) -> list[tuple[str, str]]:
    with db.connect() as conn:
        return [
            (row["content_hash"], row["path"])
            for row in conn.execute(
                "SELECT content_hash, path FROM passages"
            ).fetchall()
        ]


def test_every_passage_has_a_content_and_a_path_vector(db: Database) -> None:
    passages = _passages(db)
    assert len(passages) >= 2  # the loop below must not pass vacuously
    with db.connect() as conn:
        for chash, path in passages:
            assert get_vector(conn, chash, "emb") is not None
            path_hash = content_hash(path_body(path))
            assert get_vector(conn, path_hash, "emb") is not None


def test_passage_combined_vector_is_the_blend(db: Database) -> None:
    with db.connect() as conn:
        for chash, path in _passages(db):
            content = get_vector(conn, chash, "emb")
            path_vec = get_vector(conn, content_hash(path_body(path)), "emb")
            combined = combined_vector(conn, chash, path, "emb")
            assert combined is not None
            assert len(combined) == 2 * DIMS
            assert combined == combine(content, path_vec)  # path blend, a=0.5


def test_re_embed_is_a_no_op(db: Database, tmp_path: Path) -> None:
    with db.connect() as conn:
        before = vector_count(conn, "emb")
    embed(_job("embed"), job_context(db, tmp_path), encoder_for=fake_encoder)
    with db.connect() as conn:
        assert vector_count(conn, "emb") == before  # embed-once by content hash


def test_content_shared_by_a_section_and_its_lone_passage_embeds_once(
    db: Database,
) -> None:
    # tiny.txt is one section whose single passage has the same bytes -> same
    # content hash -> one vector, no collision (global content-hash keys).
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT s.content_hash AS sh, p.content_hash AS ph "
            "FROM sections s JOIN passages p ON p.section_id = s.id "
            "WHERE s.path = 'tiny.txt'"
        ).fetchall()
        assert rows
        for row in rows:
            if row["sh"] == row["ph"]:
                assert get_vector(conn, row["sh"], "emb") is not None
