"""A model's connection decides its completion client — map, not branch."""

import json
from dataclasses import replace
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
from hrono.jobs import store as jobs_store
from hrono.llm.claude_code import ClaudeCodeClient
from hrono.llm.client import AnthropicClient, LLMError
from hrono.llm.providers import client_for
from hrono.registry import store as registry_store
from tests.context import job_context


def _connection(conn: object, name: str, provider: str) -> None:
    registry_store.insert(
        conn,  # type: ignore[arg-type]
        "connections",
        name,
        json.dumps({"name": name, "provider": provider, "auth": {}}),
        None,
        "t",
    )


@pytest.fixture
def db(tmp_path: Path):
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        _connection(conn, "sdk", "anthropic")
        _connection(conn, "cli", "claude-code")
    yield database
    database.close()


def _model(connection: str | None) -> dict[str, object]:
    return {"name": "m", "kind": "text", "connection": connection}


def test_a_claude_code_connection_resolves_to_the_cli_client(
    db: Database, tmp_path: Path
) -> None:
    client = client_for(job_context(db, tmp_path), _model("cli"), "brief")

    assert isinstance(client.inner, ClaudeCodeClient)


def test_the_cli_client_runs_in_the_contexts_own_directory(
    db: Database, tmp_path: Path
) -> None:
    # anchored on the database like every other data path, never the
    # server's cwd — the CLI would otherwise read that project's memory.
    # assert the PROPERTY, not the path: comparing `cli_dir()` to itself, or
    # checking a parent that holds however it is computed, would pass even
    # with `cli_dir()` returning the clone cache.
    context = job_context(db, tmp_path)
    client = client_for(context, _model("cli"), "brief").inner
    cli_dir = client._workdir  # noqa: SLF001
    clones = context.cache_root

    assert cli_dir != clones  # not the clone root itself
    assert clones not in cli_dir.parents  # and not inside it
    assert cli_dir not in clones.parents  # nor an ancestor of the clones
    assert cli_dir.is_relative_to(clones.parent)  # still hrono-owned


def test_an_anthropic_connection_still_resolves_to_the_sdk_client(
    db: Database, tmp_path: Path
) -> None:
    context = job_context(
        db, tmp_path, Cipher(Fernet(Fernet.generate_key()), 1)
    )

    client = client_for(context, _model("sdk"), "brief")

    assert isinstance(client.inner, AnthropicClient)


def test_a_model_with_no_connection_keeps_the_anthropic_default(
    db: Database, tmp_path: Path
) -> None:
    # every existing database has models written before providers existed.
    context = job_context(
        db, tmp_path, Cipher(Fernet(Fernet.generate_key()), 1)
    )

    client = client_for(context, _model(None), "brief")

    assert isinstance(client.inner, AnthropicClient)


def test_an_unknown_connection_is_one_llm_error(
    db: Database, tmp_path: Path
) -> None:
    with pytest.raises(LLMError, match="unknown connection"):
        client_for(job_context(db, tmp_path), _model("ghost"), "brief")


def test_an_unsupported_provider_is_one_llm_error(
    db: Database, tmp_path: Path
) -> None:
    # a provider hrono does not serve must be told at RESOLVE time, not left
    # to fail at call time. The point is the table, so any absent name does.
    with db.connect() as conn, conn:
        _connection(conn, "future", "gemini")

    with pytest.raises(LLMError, match="unsupported provider"):
        client_for(job_context(db, tmp_path), _model("future"), "brief")


def test_the_cli_client_stops_waiting_once_its_job_is_stopped(
    db: Database, tmp_path: Path
) -> None:
    # a usage limit is waited out for hours; a run canceled meanwhile must
    # not keep its call waiting. The predicate reads the REAL jobs row.
    with db.connect() as conn, conn:
        jobs_store.insert(conn, "jw", None, None, "condense", "{}", "t")
        jobs_store.claim_next(conn, "t")
    context = replace(job_context(db, tmp_path), job_id="jw")
    wanted = client_for(context, _model("cli"), "brief").inner._wanted  # noqa: SLF001

    assert wanted() is True
    with db.connect() as conn, conn:
        jobs_store.reclaim(conn, None, "t")  # out of running, as a stop is
    assert wanted() is False
