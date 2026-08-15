from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from typer.testing import CliRunner

from hrono import cli


def keyfile(tmp_path: Path) -> Path:
    path = tmp_path / "master.key"
    path.write_bytes(Fernet.generate_key())
    return path


def test_serve_refuses_without_a_master_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("HRONO_MASTER_KEY", raising=False)
    result = CliRunner().invoke(cli.app, ["serve"])
    assert result.exit_code != 0
    assert "--key-file" in result.output
    assert "HRONO_MASTER_KEY" in result.output


def test_serve_rejects_an_invalid_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HRONO_MASTER_KEY", "not-a-valid-fernet-key")
    result = CliRunner().invoke(cli.app, ["serve"])
    assert result.exit_code != 0


def test_serve_boots_uvicorn_with_a_valid_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("HRONO_MASTER_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        cli.uvicorn, "run", lambda app, **kw: captured.update(kw, app=app)
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "serve",
            "--key-file",
            str(keyfile(tmp_path)),
            "--host",
            "0.0.0.0",
            "--port",
            "9000",
        ],
    )

    assert result.exit_code == 0
    assert captured["app"] is not None
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9000


def test_serve_defaults_to_localhost_8080(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("HRONO_MASTER_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        cli.uvicorn, "run", lambda app, **kw: captured.update(kw)
    )

    result = CliRunner().invoke(
        cli.app, ["serve", "--key-file", str(keyfile(tmp_path))]
    )

    assert result.exit_code == 0
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8080


def test_serve_refuses_a_wrong_key_with_a_clear_message_not_a_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("HRONO_MASTER_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.uvicorn, "run", lambda *a, **kw: None)

    first = tmp_path / "first.key"
    first.write_bytes(Fernet.generate_key())
    seeded = CliRunner().invoke(cli.app, ["serve", "--key-file", str(first)])
    assert seeded.exit_code == 0

    other = tmp_path / "other.key"
    other.write_bytes(Fernet.generate_key())
    result = CliRunner().invoke(cli.app, ["serve", "--key-file", str(other)])

    assert result.exit_code != 0
    assert "wrong master key" in result.output.lower()
    assert "Traceback" not in result.output


def test_serve_is_a_named_subcommand_not_the_bare_command() -> None:
    result = CliRunner().invoke(cli.app, [])
    assert result.exit_code != 0
