"""A role picks the text model; a consumer reads the producer's cache."""

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from hrono.db.database import Database
from hrono.llm.client import LLMError
from hrono.registry import store as registry_store
from hrono.registry.collections.models import Model
from hrono.summarize.resolve import producer_model_name, resolve_text_model


def _model(conn: object, name: str, role: str | None = None) -> None:
    body: dict[str, object] = {
        "name": name,
        "kind": "text",
        "connection": "c",
        "model": name,
        "params": {},
    }
    if role is not None:
        body["role"] = role
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "models",
        name,
        json.dumps(body),
        None,
        "t",
    )


@pytest.fixture
def db(tmp_path: Path) -> Iterator[Database]:
    database = Database.at(tmp_path / "hrono.db")
    yield database
    database.close()


def test_one_text_model_needs_no_role_at_all(db: Database) -> None:
    # the YAGNI default, unchanged: a one-model install configures nothing.
    with db.connect() as conn, conn:
        _model(conn, "sonnet")

    with db.connect() as conn:
        for role in ("condense", "brief", "brief-upper", "judge"):
            assert resolve_text_model(conn, {}, role)["name"] == "sonnet"


def test_a_role_picks_its_own_model(db: Database) -> None:
    with db.connect() as conn, conn:
        _model(conn, "cheap", role="condense")
        _model(conn, "smart", role="brief")

    with db.connect() as conn:
        assert resolve_text_model(conn, {}, "condense")["name"] == "cheap"
        assert resolve_text_model(conn, {}, "brief")["name"] == "smart"


def test_a_scoped_name_still_wins(db: Database) -> None:
    # an operator pinning one run beats the configured mapping.
    with db.connect() as conn, conn:
        _model(conn, "cheap", role="condense")
        _model(conn, "smart", role="brief")

    with db.connect() as conn:
        scope = {"type": "model", "name": "smart"}
        assert resolve_text_model(conn, scope, "condense")["name"] == "smart"


def test_two_models_and_no_mapping_is_an_error_naming_the_role(
    db: Database,
) -> None:
    with db.connect() as conn, conn:
        _model(conn, "a")
        _model(conn, "b")

    with db.connect() as conn, pytest.raises(LLMError, match="condense"):
        resolve_text_model(conn, {}, "condense")


def test_two_models_claiming_one_role_is_an_error(db: Database) -> None:
    with db.connect() as conn, conn:
        _model(conn, "a", role="brief")
        _model(conn, "b", role="brief")

    with db.connect() as conn, pytest.raises(LLMError, match="role: brief"):
        resolve_text_model(conn, {}, "brief")


def test_the_consumer_reads_the_producers_model_name(db: Database) -> None:
    # THE LANDMINE. `brief` reduces the condensations `condense` wrote,
    # and they are keyed by the CONDENSE model's name. While one text model
    # served both, the two names matched and the join worked. With a cheap
    # condense model and a smart brief model, briefing under its own name finds
    # NO condensations and silently summarises nothing.
    with db.connect() as conn, conn:
        _model(conn, "cheap", role="condense")
        _model(conn, "smart", role="brief")

    with db.connect() as conn:
        assert resolve_text_model(conn, {}, "brief")["name"] == "smart"
        assert producer_model_name(conn, {}, "condense") == "cheap"


def test_an_invalid_role_is_refused_at_write_time(db: Database) -> None:
    # a typo'd role is config that validates and then does nothing — the
    # model is never selected for any stage, and the operator believes they
    # configured a mapping. Same bar as a connection's validation: refuse at
    # WRITE time, never at condense time.
    with pytest.raises(ValidationError):
        Model(
            name="oops",
            kind="text",
            connection="c",
            model="m",
            role="condence",  # type: ignore[arg-type]
        )
