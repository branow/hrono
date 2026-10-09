"""Maintain checks it can brief before it spends the ingest budget.

On hrono's own repository, a missing text model is otherwise found only after
cloning, splitting 394 sections and embedding 4321 vectors — minutes — and
then failing with `llm-error: no text model available`, which is knowable at
second zero.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hrono.db.database import Database
from hrono.errors import DomainError
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.registry import store as registry_store
from hrono.tree.maintain import maintain

TREE = "default"


def _job() -> Job:
    return Job(
        id="m1",
        parent_id=None,
        tree=TREE,
        op="maintain",
        scope={},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


def _model(name: str, kind: str, role: str | None = None) -> str:
    return json.dumps(
        {
            "name": name,
            "kind": kind,
            "connection": None,
            "model": "m",
            "role": role,
            "params": {"dims": 4},
        }
    )


@pytest.fixture
def db(tmp_path: Path) -> Database:
    return Database.at(tmp_path / "hrono.db")


def _sections(database: Database) -> int:
    with database.connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0])


def test_no_model_at_all_fails_before_anything_is_ingested(
    db: Database,
) -> None:
    with pytest.raises(DomainError) as raised:
        maintain(_job(), JobContext(db))

    assert "model" in str(raised.value)
    assert _sections(db) == 0


def test_an_embedding_model_alone_is_not_enough(db: Database) -> None:
    """Embeddings configured, briefs not.

    That install ingests and embeds happily and then cannot write a word.
    """
    with db.connect() as conn, conn:
        registry_store.insert(
            conn, "models", "emb", _model("emb", "embedding"), None, "t"
        )

    with pytest.raises(DomainError) as raised:
        maintain(_job(), JobContext(db))

    assert "text model" in str(raised.value)
    assert _sections(db) == 0


def test_a_missing_role_is_named(db: Database) -> None:
    # condense, brief and brief-upper are three different asks, and an install
    # with two of them should be told which one is missing
    with db.connect() as conn, conn:
        registry_store.insert(
            conn, "models", "emb", _model("emb", "embedding"), None, "t"
        )
        for role in ("condense", "brief"):
            registry_store.insert(
                conn,
                "models",
                f"w-{role}",
                _model(f"w-{role}", "text", role),
                None,
                "t",
            )

    with pytest.raises(DomainError) as raised:
        maintain(_job(), JobContext(db))

    assert "brief-upper" in str(raised.value)


def test_the_check_adds_no_requirement_the_chain_did_not_have(
    db: Database,
) -> None:
    """An injected client does NOT exempt it, and that costs nothing.

    The stages resolve these models whatever completion they are handed —
    `condense` asks for its text model before it checks whether there is
    anything to condense — so the precondition only moves the failure earlier.
    A one-model install satisfies every role, which is the fallback
    `resolve_text_model` has always had.
    """
    with db.connect() as conn, conn:
        registry_store.insert(
            conn, "models", "emb", _model("emb", "embedding"), None, "t"
        )
        registry_store.insert(
            conn, "models", "sole", _model("sole", "text"), None, "t"
        )
        # `hrono serve` seeds these on first run; a bare Database has
        # none, and they are a precondition the stages have always had.
        for role in ("condense", "brief", "brief-upper"):
            registry_store.insert(
                conn,
                "prompts",
                role,
                json.dumps(
                    {"name": role, "role": role, "template": "X {content}"}
                ),
                None,
                "t",
            )

    class Fake:
        def complete(self, request: object) -> object:  # pragma: no cover
            raise AssertionError("not reached: the tree has no sources")

    maintain(_job(), JobContext(db), client=Fake())
