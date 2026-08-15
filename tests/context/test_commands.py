from pathlib import Path

import pytest
from typer.testing import CliRunner

from hrono import cli

TOKEN = "sekret-bearer-token"


def run(monkeypatch: pytest.MonkeyPatch, home: Path, *args: str) -> object:
    monkeypatch.setenv("HRONO_HOME", str(home))
    return CliRunner().invoke(cli.app, ["context", *args])


def test_add_writes_config_and_marks_first_current(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    added = run(
        monkeypatch,
        tmp_path,
        "add",
        "prod",
        "--server",
        "https://p",
        "--token",
        TOKEN,
    )
    assert added.exit_code == 0
    assert (tmp_path / "config.toml").exists()

    listed = run(monkeypatch, tmp_path, "list")
    assert listed.exit_code == 0
    assert "* prod" in listed.output


def test_second_add_does_not_change_current(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run(
        monkeypatch,
        tmp_path,
        "add",
        "prod",
        "--server",
        "https://p",
        "--token",
        "t1",
    )
    run(
        monkeypatch,
        tmp_path,
        "add",
        "dev",
        "--server",
        "https://d",
        "--token",
        "t2",
    )
    listed = run(monkeypatch, tmp_path, "list")
    assert "* prod" in listed.output
    assert "  dev" in listed.output


def test_duplicate_add_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run(
        monkeypatch,
        tmp_path,
        "add",
        "prod",
        "--server",
        "https://p",
        "--token",
        "t1",
    )
    dup = run(
        monkeypatch,
        tmp_path,
        "add",
        "prod",
        "--server",
        "https://x",
        "--token",
        "t2",
    )
    assert dup.exit_code != 0
    assert "already exists" in dup.output


def test_use_switches_and_unknown_use_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run(
        monkeypatch,
        tmp_path,
        "add",
        "prod",
        "--server",
        "https://p",
        "--token",
        "t1",
    )
    run(
        monkeypatch,
        tmp_path,
        "add",
        "dev",
        "--server",
        "https://d",
        "--token",
        "t2",
    )
    assert run(monkeypatch, tmp_path, "use", "dev").exit_code == 0
    assert "* dev" in run(monkeypatch, tmp_path, "list").output
    assert run(monkeypatch, tmp_path, "use", "ghost").exit_code != 0


def test_current_reports_without_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run(
        monkeypatch,
        tmp_path,
        "add",
        "prod",
        "--server",
        "https://p",
        "--token",
        TOKEN,
    )
    current = run(monkeypatch, tmp_path, "current")
    assert current.exit_code == 0
    assert "prod" in current.output
    assert "https://p" in current.output
    assert TOKEN not in current.output


def test_current_when_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    current = run(monkeypatch, tmp_path, "current")
    assert current.exit_code == 0
    assert "No current context" in current.output


def test_list_empty_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    listed = run(monkeypatch, tmp_path, "list")
    assert listed.exit_code == 0
    assert "No contexts" in listed.output


def test_rm_removes_and_clears_current(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run(
        monkeypatch,
        tmp_path,
        "add",
        "prod",
        "--server",
        "https://p",
        "--token",
        "t1",
    )
    removed = run(monkeypatch, tmp_path, "rm", "prod")
    assert removed.exit_code == 0
    assert "no context is current" in removed.output.lower()
    assert run(monkeypatch, tmp_path, "rm", "ghost").exit_code != 0


def test_token_never_leaks_across_commands(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    run(
        monkeypatch,
        tmp_path,
        "add",
        "prod",
        "--server",
        "https://p",
        "--token",
        TOKEN,
    )
    for args in (["list"], ["current"], ["use", "prod"]):
        assert TOKEN not in run(monkeypatch, tmp_path, *args).output
