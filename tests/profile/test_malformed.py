from pathlib import Path

import pytest
from typer.testing import CliRunner

from hrono import cli

TOKEN = "sekret-token-value"


def write_config(home: Path, text: str) -> None:
    home.mkdir(parents=True, exist_ok=True)
    (home / "config.toml").write_text(text)


def run(monkeypatch: pytest.MonkeyPatch, home: Path, *args: str) -> object:
    monkeypatch.setenv("HRONO_HOME", str(home))
    return CliRunner().invoke(cli.app, ["profile", *args])


INVALID_TOML = "this is = not valid toml ["
WRONG_SHAPE = (
    'current = "prod"\n[profiles.prod]\nserver_url = 42\ntoken = "'
    + TOKEN
    + '"\n'
)


def test_error_never_contains_the_token(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_config(tmp_path, WRONG_SHAPE)
    result = run(monkeypatch, tmp_path, "current")
    assert result.exit_code != 0
    assert TOKEN not in result.output


@pytest.mark.parametrize(
    "text", [INVALID_TOML, WRONG_SHAPE], ids=["invalid-toml", "wrong-shape"]
)
def test_every_command_reports_malformed_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str
) -> None:
    write_config(tmp_path, text)
    failures = []
    for args in (
        ["list"],
        ["current"],
        ["use", "prod"],
        ["rm", "prod", "--force"],
        ["add", "x", "--server", "u", "--token", "t"],
    ):
        result = run(monkeypatch, tmp_path, *args)
        clean = (
            result.exit_code != 0
            and "Malformed config" in result.output
            and "Traceback" not in result.output
            and not isinstance(result.exception, KeyError)
        )
        if not clean:
            failures.append(f"{' '.join(args)}: {result.output!r}")
    assert failures == []


def test_well_formed_config_still_works(
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
    listed = run(monkeypatch, tmp_path, "list")
    assert listed.exit_code == 0
    assert "* prod" in listed.output
    assert TOKEN not in listed.output
