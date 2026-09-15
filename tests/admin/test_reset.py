from pathlib import Path

import pytest
from typer.testing import CliRunner

from hrono import cli
from hrono.admin.reset import (
    LinkedCache,
    NotHronoDatabase,
    ResetIncomplete,
    targets,
    wipe,
)
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


def test_reset_removes_the_cache_and_the_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # F32: reset claimed to destroy ingested content but left the clones, so
    # the next "fresh start" diffed against 10 MB of orphaned trees.
    monkeypatch.chdir(tmp_path)
    conn = open_database(DEFAULT_PATH)
    conn.close()
    DEFAULT_PATH.with_name(DEFAULT_PATH.name + ".lock").write_bytes(b"")
    clone = DEFAULT_PATH.parent / "cache" / "sources" / "repo"
    clone.mkdir(parents=True)
    (clone / "a.txt").write_text("cloned bytes")

    removed = wipe(DEFAULT_PATH)

    assert clone.parent.parent in removed
    assert not clone.exists()
    assert not DEFAULT_PATH.with_name(DEFAULT_PATH.name + ".lock").exists()
    assert not DEFAULT_PATH.exists()


def test_reset_targets_report_the_cache_before_deleting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    conn = open_database(DEFAULT_PATH)
    conn.close()
    (DEFAULT_PATH.parent / "cache" / "sources").mkdir(parents=True)
    listed = targets(DEFAULT_PATH)
    assert DEFAULT_PATH.parent / "cache" in listed


def _hrono_db(root: Path) -> Path:
    db_path = root / ".hrono" / "hrono.db"
    db_path.parent.mkdir(parents=True)
    open_database(db_path).close()
    return db_path


def test_a_symlinked_cache_is_refused_before_anything_is_deleted(
    tmp_path: Path,
) -> None:
    # rmtree refuses a top-level symlink BY DESIGN, and the database is removed
    # first, so an unguarded wipe destroyed the database and then raised —
    # leaving the operator with no database, the clones intact, and no report.
    db_path = _hrono_db(tmp_path)
    elsewhere = tmp_path / "volume" / "cache"
    (elsewhere / "sources" / "repo").mkdir(parents=True)
    (elsewhere / "sources" / "repo" / "f.txt").write_text("cloned")
    (db_path.parent / "cache").symlink_to(elsewhere)

    with pytest.raises(LinkedCache) as caught:
        wipe(db_path)

    assert "symlink" in caught.value.message
    assert db_path.exists()  # nothing was destroyed
    assert (elsewhere / "sources" / "repo" / "f.txt").read_text() == "cloned"


def test_the_cli_refuses_a_symlinked_cache_without_a_traceback(
    tmp_path: Path,
) -> None:
    db_path = _hrono_db(tmp_path)
    elsewhere = tmp_path / "volume" / "cache"
    (elsewhere / "sources").mkdir(parents=True)
    (db_path.parent / "cache").symlink_to(elsewhere)

    result = runner.invoke(cli.app, ["reset", "--force", "--db", str(db_path)])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "symlink" in result.output
    assert db_path.exists()
    assert elsewhere.exists()


def test_a_wipe_that_stops_part_way_still_reports_what_it_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = _hrono_db(tmp_path)
    (db_path.parent / "cache" / "sources").mkdir(parents=True)
    real = Path.unlink

    def fail_on_the_lock(self: Path, *args: object, **kwargs: object) -> None:
        if self.name.endswith(".lock"):
            raise PermissionError(13, "Permission denied")
        real(self, *args, **kwargs)

    db_path.with_name(db_path.name + ".lock").write_bytes(b"")
    monkeypatch.setattr(Path, "unlink", fail_on_the_lock)

    with pytest.raises(ResetIncomplete) as caught:
        wipe(db_path)

    assert caught.value.details is not None
    assert caught.value.details["removed"] == [str(db_path)]
    assert str(db_path) in caught.value.message or "stopped at" in (
        caught.value.message
    )


def test_the_cli_prints_the_removals_of_a_partial_wipe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the report is what an operator plans recovery from; losing it while the
    # database is already gone is the real harm.
    db_path = _hrono_db(tmp_path)
    db_path.with_name(db_path.name + ".lock").write_bytes(b"")
    real = Path.unlink

    def fail_on_the_lock(self: Path, *args: object, **kwargs: object) -> None:
        if self.name.endswith(".lock"):
            raise PermissionError(13, "Permission denied")
        real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_on_the_lock)

    result = runner.invoke(cli.app, ["reset", "--force", "--db", str(db_path)])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "Removed:" in result.output
    assert str(db_path) in result.output
    assert "Permission denied" in result.output
