from pathlib import Path

import pytest
from typer.testing import CliRunner

from hrono import cli
from hrono.admin.reset import NotHronoDatabase, wipe
from hrono.auth.bootstrap import bootstrap_admin
from hrono.auth.users import create_user, list_users
from hrono.db.database import DEFAULT_PATH, open_database

runner = CliRunner()


def _seed_db() -> None:
    conn = open_database(DEFAULT_PATH)
    create_user(conn, "admin", "admin")
    conn.close()
    # fabricate the SQLite sidecars so the wipe has all three to remove
    for suffix in ("-wal", "-shm"):
        DEFAULT_PATH.with_name(DEFAULT_PATH.name + suffix).write_bytes(b"x")


@pytest.fixture
def in_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_force_wipes_db_and_sidecars_and_allows_rebootstrap(
    in_tmp: Path,
) -> None:
    _seed_db()
    result = runner.invoke(cli.app, ["reset", "--force"])
    assert result.exit_code == 0
    assert not DEFAULT_PATH.exists()
    assert not DEFAULT_PATH.with_name(DEFAULT_PATH.name + "-wal").exists()
    assert not DEFAULT_PATH.with_name(DEFAULT_PATH.name + "-shm").exists()
    # a fresh open re-applies migrations and bootstrap mints a new admin
    conn = open_database(DEFAULT_PATH)
    token = bootstrap_admin(conn)
    assert token is not None
    assert {u.name for u in list_users(conn)} == {"admin"}
    conn.close()


def test_confirmed_prompt_wipes(in_tmp: Path) -> None:
    _seed_db()
    result = runner.invoke(cli.app, ["reset"], input="y\n")
    assert result.exit_code == 0
    assert not DEFAULT_PATH.exists()


def test_declined_prompt_changes_nothing_and_exits_nonzero(
    in_tmp: Path,
) -> None:
    _seed_db()
    result = runner.invoke(cli.app, ["reset"], input="n\n")
    assert result.exit_code != 0
    assert "abort" in result.output.lower()
    assert DEFAULT_PATH.exists()  # untouched


def test_missing_database_is_a_noop_exit_zero(in_tmp: Path) -> None:
    assert not DEFAULT_PATH.exists()
    result = runner.invoke(cli.app, ["reset", "--force"])
    assert result.exit_code == 0
    assert "nothing to reset" in result.output.lower()


def test_only_known_files_are_removed(in_tmp: Path) -> None:
    _seed_db()
    bystander = DEFAULT_PATH.with_name("keep.txt")
    bystander.write_text("do not delete me")
    result = runner.invoke(cli.app, ["reset", "--force"])
    assert result.exit_code == 0
    assert bystander.exists()
    assert bystander.read_text() == "do not delete me"


def test_wipe_refuses_a_non_hrono_path(tmp_path: Path) -> None:
    stray = tmp_path / "random.txt"
    stray.write_text("important")
    with pytest.raises(NotHronoDatabase):
        wipe(stray)
    assert stray.exists()


def test_reset_needs_no_token_or_key_and_reports_removed(in_tmp: Path) -> None:
    _seed_db()
    result = runner.invoke(cli.app, ["reset", "--force"])
    assert result.exit_code == 0
    assert str(DEFAULT_PATH) in result.output
    assert "Removed:" in result.output


def test_help_documents_recovery_and_data_loss() -> None:
    result = runner.invoke(cli.app, ["reset", "--help"])
    assert result.exit_code == 0
    lower = result.output.lower()
    assert "destroys all data" in lower
    assert "lockout" in lower or "recover" in lower
