"""T44: a model's connection decides its completion client — map, not branch."""

import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from hrono.crypto.cipher import Cipher
from hrono.db.database import Database
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
    client = client_for(job_context(db, tmp_path), _model("cli"))

    assert isinstance(client, ClaudeCodeClient)


def test_the_cli_client_runs_in_the_contexts_own_directory(
    db: Database, tmp_path: Path
) -> None:
    # anchored on the database like every other data path (#098), never the
    # server's cwd — the CLI would otherwise read that project's memory.
    context = job_context(db, tmp_path)
    client = client_for(context, _model("cli"))

    assert client._workdir == context.cli_dir()  # noqa: SLF001
    assert (
        context.cli_dir().parent == context.cache_root.parent.parent / "cache"
    )


def test_an_anthropic_connection_still_resolves_to_the_sdk_client(
    db: Database, tmp_path: Path
) -> None:
    context = job_context(
        db, tmp_path, Cipher(Fernet(Fernet.generate_key()), 1)
    )

    assert isinstance(client_for(context, _model("sdk")), AnthropicClient)


def test_a_model_with_no_connection_keeps_the_anthropic_default(
    db: Database, tmp_path: Path
) -> None:
    # every existing database has models written before providers existed.
    context = job_context(
        db, tmp_path, Cipher(Fernet(Fernet.generate_key()), 1)
    )

    assert isinstance(client_for(context, _model(None)), AnthropicClient)


def test_an_unknown_connection_is_one_llm_error(
    db: Database, tmp_path: Path
) -> None:
    with pytest.raises(LLMError, match="unknown connection"):
        client_for(job_context(db, tmp_path), _model("ghost"))


def test_an_unsupported_provider_is_one_llm_error(
    db: Database, tmp_path: Path
) -> None:
    # openai / openai-compatible are later MAP ENTRIES (T44.1/T44.3), and until
    # then a user who registers one must be told, not left to fail at call time.
    with db.connect() as conn, conn:
        _connection(conn, "future", "openai")

    with pytest.raises(LLMError, match="unsupported provider"):
        client_for(job_context(db, tmp_path), _model("future"))
