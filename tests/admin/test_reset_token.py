from pathlib import Path

import pytest
from typer.testing import CliRunner

from hrono import cli
from hrono.auth.users import authenticate, create_user, get_user
from hrono.db.database import DEFAULT_PATH, open_database

runner = CliRunner()


def _token(output: str) -> str:
    for line in output.splitlines():
        stripped = line.strip()
        if stripped.startswith("token:"):
            return stripped.split("token:", 1)[1].strip()
    raise AssertionError(f"no token in output:\n{output}")


@pytest.fixture
def seeded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    monkeypatch.chdir(tmp_path)
    conn = open_database(DEFAULT_PATH)
    tokens = {
        name: create_user(conn, name, role)[1]
        for name, role in (("admin", "admin"), ("reader", "reader"))
    }
    conn.close()
    return tokens


def test_reissue_rotates_the_token_old_fails_new_works(
    seeded: dict[str, str],
) -> None:
    old = seeded["admin"]
    result = runner.invoke(cli.app, ["admin", "reset-token", "admin"])
    assert result.exit_code == 0
    assert "once" in result.output.lower()
    assert "Bearer" in result.output
    new = _token(result.output)
    assert new != old
    conn = open_database(DEFAULT_PATH)
    assert authenticate(conn, old) is None
    reissued = authenticate(conn, new)
    assert reissued is not None
    assert reissued.name == "admin"
    assert reissued.role == "admin"
    conn.close()


def test_only_the_target_row_changes(seeded: dict[str, str]) -> None:
    conn = open_database(DEFAULT_PATH)
    before = get_user(conn, "admin")
    conn.close()

    result = runner.invoke(cli.app, ["admin", "reset-token", "admin"])
    assert result.exit_code == 0

    conn = open_database(DEFAULT_PATH)
    # the other user's token still authenticates
    assert authenticate(conn, seeded["reader"]) is not None
    # target user's non-secret columns are untouched
    after = get_user(conn, "admin")
    assert after == before
    conn.close()


def test_unknown_user_is_a_clean_error(seeded: dict[str, str]) -> None:
    result = runner.invoke(cli.app, ["admin", "reset-token", "ghost"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()
    assert "Traceback" not in result.output


def test_missing_database_says_nothing_to_reset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert not DEFAULT_PATH.exists()
    result = runner.invoke(cli.app, ["admin", "reset-token", "admin"])
    assert result.exit_code != 0
    lower = result.output.lower()
    assert "nothing to reset" in lower or "serve" in lower
    assert "Traceback" not in result.output


def test_new_token_is_never_stored_or_shown_in_plaintext(
    seeded: dict[str, str],
) -> None:
    result = runner.invoke(cli.app, ["admin", "reset-token", "reader"])
    assert result.exit_code == 0
    new = _token(result.output)

    conn = open_database(DEFAULT_PATH)
    row = conn.execute(
        "SELECT token_hash FROM users WHERE name = ?", ("reader",)
    ).fetchone()
    conn.close()
    assert row["token_hash"] != new
    assert new.encode() not in DEFAULT_PATH.read_bytes()


def test_help_documents_the_local_auth_bypass() -> None:
    result = runner.invoke(cli.app, ["admin", "--help"])
    assert result.exit_code == 0
    lower = result.output.lower()
    assert "bypass" in lower
    assert "filesystem" in lower
