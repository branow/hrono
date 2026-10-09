"""A text model on a `claude-code` connection validates through the CLI.

Driven through the endpoint with a real subprocess: a stand-in `claude` on PATH
is the only fake, so the dispatch, the working directory and the error path run
as production runs them. The README's first-run path depends on this.
"""

import inspect
import json
import sqlite3
import stat
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
from hrono.registry.validation import model_validation
from hrono.registry.validation.model_validation import validate_model
from hrono.server.app import create_app

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
OK = json.dumps({"subtype": "success", "is_error": False, "result": "hi"})


def fake_claude(directory: Path, script: str) -> None:
    """A `claude` that answers `--version` and otherwise runs ``script``."""
    binary = directory / "claude"
    binary.write_text(
        '#!/bin/sh\n[ "$1" = "--version" ] && echo 2.1 && exit 0\n' + script
    )
    binary.chmod(binary.stat().st_mode | stat.S_IEXEC)


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
        fake_claude(bin_dir, "exit 0\n")
        assert (
            client.post("/connections", json=CONNECTION, headers=headers)
        ).status_code == 201
        yield client, headers, bin_dir


def test_a_text_model_registers_through_the_cli(served, tmp_path: Path) -> None:
    client, headers, bin_dir = served
    fake_claude(
        bin_dir,
        f"cat >/dev/null\necho '{OK}'\n",
    )

    response = client.post("/models", json=TEXT, headers=headers)

    assert response.status_code == 201, response.text
    with closing(sqlite3.connect(tmp_path / "data" / "hrono.db")) as conn:
        rows = conn.execute("SELECT role, provider, ok FROM llm_calls")
        assert rows.fetchall() == [("validate", "claude-code", 1)]


def test_the_probe_runs_from_the_directory_hrono_owns(
    served, tmp_path: Path
) -> None:
    client, headers, bin_dir = served
    seen = tmp_path / "cwd"
    fake_claude(
        bin_dir,
        f"pwd > {seen}\ncat >/dev/null\necho '{OK}'\n",
    )

    client.post("/models", json=TEXT, headers=headers)

    assert (
        Path(seen.read_text().strip()).resolve()
        == cli_workdir(tmp_path / "data" / "hrono.db").resolve()
    )


def test_a_broken_cli_is_an_actionable_bad_request(served) -> None:
    client, headers, bin_dir = served
    fake_claude(
        bin_dir,
        "echo 'not logged in' >&2\nexit 1\n",
    )

    response = client.post("/models", json=TEXT, headers=headers)

    assert response.status_code == 400
    detail = response.text
    assert "claude CLI" in detail and "not logged in" in detail
    assert "http" not in detail.lower()


def test_an_empty_answer_is_rejected(served) -> None:
    client, headers, bin_dir = served
    empty = json.dumps({"subtype": "success", "is_error": False, "result": ""})
    fake_claude(
        bin_dir,
        f"cat >/dev/null\necho '{empty}'\n",
    )

    assert client.post("/models", json=TEXT, headers=headers).status_code == 400


def test_the_registered_model_reaches_the_cli(served, tmp_path: Path) -> None:
    client, headers, bin_dir = served
    argv = tmp_path / "argv"
    fake_claude(
        bin_dir,
        f"echo \"$@\" > {argv}\ncat >/dev/null\necho '{OK}'\n",
    )

    client.post("/models", json=TEXT, headers=headers)

    assert "--model haiku" in argv.read_text()


def test_a_hung_cli_ends_in_a_bad_request(served) -> None:
    client, _, bin_dir = served
    state = client.app.state
    context = ValidationContext(
        database=state.db,
        cipher=state.cipher,
        cache_root=state.cache_root,
    )
    fake_claude(bin_dir, "sleep 5\n")

    started = time.monotonic()
    with pytest.raises(ValidationFailed, match="timed out"):
        validate_model(dict(TEXT), context, cli_timeout=0.5)

    assert time.monotonic() - started < 4


def test_the_real_probe_limit_ends_before_the_client_stops_waiting() -> None:
    assert model_validation._CLI_TIMEOUT < WRITE_TIMEOUT


def test_validate_models_own_default_ends_before_the_client_waits() -> None:
    default = inspect.signature(validate_model).parameters["cli_timeout"]

    assert default.default < WRITE_TIMEOUT
