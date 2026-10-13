"""A text model on a `claude-code` connection validates through the CLI.

Driven through the endpoint with the real Agent SDK and a real subprocess: a
stand-in `claude` on PATH is the only fake, so the dispatch, the working
directory and the error path run as production runs them. The README's
first-run path depends on this.
"""

import inspect
import sqlite3
import time
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from hrono.auth.users import create_user
from hrono.crypto.masterkey import reconcile
from hrono.db.database import open_database
from hrono.paths import cli_workdir
from hrono.registry.commands import WRITE_TIMEOUT
from hrono.registry.descriptor import ValidationContext, ValidationFailed
from hrono.registry.validation.model_validation import validate_model
from hrono.server.app import create_app
from tests.claude_stub import calls, result, stub_claude

KEY = Fernet.generate_key()
CONNECTION = {
    "name": "cli",
    "provider": "claude-code",
    "auth": {"method": "none"},
}
TEXT = {
    "name": "haiku",
    "kind": "text",
    "connection": "cli",
    "model": "haiku",
}
OK = result("hi")


@pytest.fixture
def served(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[TestClient, dict[str, str], Path]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", f"{bin_dir}:/usr/bin:/bin")
    db_path = tmp_path / "data" / "hrono.db"
    db_path.parent.mkdir()
    conn = open_database(db_path)
    reconcile(conn, KEY)
    token = create_user(conn, "writer", "writer")[1]
    conn.close()
    app = create_app(db_path=db_path, master_key=KEY)
    headers = {"Authorization": f"Bearer {token}"}
    with TestClient(app) as client:
        stub_claude(bin_dir, answer=OK)
        assert (
            client.post("/connections", json=CONNECTION, headers=headers)
        ).status_code == 201
        yield client, headers, bin_dir


def test_a_text_model_registers_through_the_cli(served, tmp_path: Path) -> None:
    client, headers, bin_dir = served
    stub_claude(bin_dir, answer=OK)

    response = client.post("/models", json=TEXT, headers=headers)

    assert response.status_code == 201, response.text
    with closing(sqlite3.connect(tmp_path / "data" / "hrono.db")) as conn:
        rows = conn.execute("SELECT role, provider, ok FROM llm_calls")
        assert rows.fetchall() == [("validate", "claude-code", 1)]


def test_the_probe_runs_from_the_directory_hrono_owns(
    served, tmp_path: Path
) -> None:
    client, headers, bin_dir = served
    stub_claude(bin_dir, answer=OK)

    client.post("/models", json=TEXT, headers=headers)

    [call] = calls(bin_dir)
    assert (
        Path(str(call["cwd"])).resolve()
        == cli_workdir(tmp_path / "data" / "hrono.db").resolve()
    )


def test_a_broken_cli_is_an_actionable_bad_request(served) -> None:
    client, headers, bin_dir = served
    stub_claude(bin_dir, exit=1, stderr="not logged in\n")

    response = client.post("/models", json=TEXT, headers=headers)

    assert response.status_code == 400
    detail = response.text
    assert "claude CLI" in detail and "not logged in" in detail
    assert "http" not in detail.lower()


def test_an_empty_answer_is_rejected(served) -> None:
    client, headers, bin_dir = served
    stub_claude(bin_dir, answer=result(""))

    assert client.post("/models", json=TEXT, headers=headers).status_code == 400


def test_the_registered_model_reaches_the_cli(served, tmp_path: Path) -> None:
    client, headers, bin_dir = served
    stub_claude(bin_dir, answer=OK)

    client.post("/models", json=TEXT, headers=headers)

    [call] = calls(bin_dir)
    assert "--model haiku" in " ".join(call["argv"])  # type: ignore[arg-type]


def test_a_hung_cli_ends_in_a_bad_request(served) -> None:
    client, _, bin_dir = served
    state = client.app.state
    context = ValidationContext(
        database=state.db,
        cipher=state.cipher,
        cache_root=state.cache_root,
    )
    stub_claude(bin_dir, answer=OK, sleep=60)

    started = time.monotonic()
    with pytest.raises(ValidationFailed, match="timed out"):
        validate_model(dict(TEXT), context, cli_timeout=0.5)

    assert time.monotonic() - started < 0.5 + SHUTDOWN_GRACE + 3


# The SDK gives a CLI it is done with 5 s to exit on its own before it
# terminates it, so a timed-out call returns that much after its deadline.
SHUTDOWN_GRACE = 5.0


def test_validate_models_own_default_ends_before_the_client_waits() -> None:
    default = inspect.signature(validate_model).parameters["cli_timeout"]

    assert default.default + SHUTDOWN_GRACE < WRITE_TIMEOUT
