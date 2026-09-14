"""#098: every data location hangs off the database file, not the cwd."""

from pathlib import Path

import pytest

from hrono.db.database import DEFAULT_PATH
from hrono.paths import ENV_DB, cache_root, database_path


def test_explicit_db_wins_over_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_DB, str(tmp_path / "env" / "hrono.db"))
    chosen = database_path(tmp_path / "flag" / "hrono.db")
    assert chosen == tmp_path / "flag" / "hrono.db"


def test_the_environment_wins_over_the_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_DB, str(tmp_path / "env" / "hrono.db"))
    assert database_path() == tmp_path / "env" / "hrono.db"


def test_the_default_is_used_when_nothing_is_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(ENV_DB, raising=False)
    monkeypatch.chdir(tmp_path)
    assert database_path() == tmp_path.resolve() / DEFAULT_PATH


def test_a_resolved_path_survives_a_later_chdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the anchor is read once at startup: resolving it there is what stops a
    # later working directory from moving the database or its cache (F25).
    monkeypatch.delenv(ENV_DB, raising=False)
    monkeypatch.chdir(tmp_path)
    before = database_path()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    assert before.is_absolute()
    assert cache_root(before) == tmp_path.resolve() / ".hrono/cache/sources"


def test_the_cache_hangs_off_the_database_directory(tmp_path: Path) -> None:
    assert cache_root(tmp_path / "a" / "hrono.db") == (
        tmp_path / "a" / "cache" / "sources"
    )
