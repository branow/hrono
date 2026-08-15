import pytest
from typer.testing import CliRunner

from hrono import cli


def test_serve_boots_uvicorn_with_the_app_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(target: str, **kwargs: object) -> None:
        captured["target"] = target
        captured.update(kwargs)

    monkeypatch.setattr(cli.uvicorn, "run", fake_run)

    result = CliRunner().invoke(
        cli.app, ["serve", "--host", "0.0.0.0", "--port", "9000"]
    )

    assert result.exit_code == 0
    assert captured["target"] == "hrono.server.app:create_app"
    assert captured["factory"] is True
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 9000


def test_serve_defaults_to_localhost_8080(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        cli.uvicorn, "run", lambda target, **kw: captured.update(kw)
    )

    result = CliRunner().invoke(cli.app, ["serve"])

    assert result.exit_code == 0
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8080


def test_serve_is_a_named_subcommand_not_the_bare_command() -> None:
    result = CliRunner().invoke(cli.app, [])
    assert result.exit_code != 0
