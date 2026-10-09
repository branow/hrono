from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from typer.testing import CliRunner

from hrono import cli
from hrono.auth.users import authenticate
from hrono.db.database import DEFAULT_PATH, open_database
from hrono.db.lock import exclusive
from hrono.paths import ENV_DB, cache_root


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


def _token_from(output: str) -> str:
    for line in output.splitlines():
        if "token:" in line:
            return line.split("token:", 1)[1].strip()
    raise AssertionError("no token line in output")


def test_first_serve_bootstraps_admin_and_prints_token_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("HRONO_MASTER_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli.uvicorn, "run", lambda *a, **kw: None)
    key = tmp_path / "master.key"
    key.write_bytes(Fernet.generate_key())

    first = CliRunner().invoke(cli.app, ["serve", "--key-file", str(key)])
    assert first.exit_code == 0
    assert "admin" in first.output
    assert "once" in first.output.lower()
    assert "hrono profile add" in first.output  # primary CLI path
    assert "Bearer" in first.output  # secondary direct-API note

    conn = open_database(tmp_path / ".hrono" / "hrono.db")
    user = authenticate(conn, _token_from(first.output))
    conn.close()
    assert user is not None
    assert user.name == "admin"
    assert user.role == "admin"

    second = CliRunner().invoke(cli.app, ["serve", "--key-file", str(key)])
    assert second.exit_code == 0
    assert "Bearer" not in second.output


def test_serve_is_a_named_subcommand_not_the_bare_command() -> None:
    result = CliRunner().invoke(cli.app, [])
    assert result.exit_code != 0


def test_a_second_serve_on_the_same_database_is_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("HRONO_MASTER_KEY", raising=False)
    monkeypatch.chdir(tmp_path)
    started: list[object] = []
    monkeypatch.setattr(cli.uvicorn, "run", lambda *a, **kw: started.append(a))

    with exclusive(DEFAULT_PATH):
        result = CliRunner().invoke(
            cli.app, ["serve", "--key-file", str(keyfile(tmp_path))]
        )

    assert result.exit_code != 0
    assert started == []  # no second worker loop against the same file
    assert "already using" in result.output
    assert "Traceback" not in result.output


def test_serve_db_flag_anchors_the_database_and_its_cache(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # without --db the location must not be "whatever cwd the operator is in".
    monkeypatch.delenv("HRONO_MASTER_KEY", raising=False)
    monkeypatch.delenv(ENV_DB, raising=False)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    db_path = tmp_path / "data" / ".hrono" / "hrono.db"
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        cli.uvicorn, "run", lambda app, **kw: captured.update(kw, app=app)
    )

    result = CliRunner().invoke(
        cli.app,
        ["serve", "--key-file", str(keyfile(tmp_path)), "--db", str(db_path)],
    )

    assert result.exit_code == 0
    assert db_path.exists()  # created where --db says, not under the cwd
    assert not (elsewhere / ".hrono").exists()
    assert cache_root(db_path) == db_path.parent / "cache" / "sources"


def test_serve_reads_the_database_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("HRONO_MASTER_KEY", raising=False)
    db_path = tmp_path / "env" / ".hrono" / "hrono.db"
    monkeypatch.setenv(ENV_DB, str(db_path))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    monkeypatch.setattr(cli.uvicorn, "run", lambda app, **kw: None)

    result = CliRunner().invoke(
        cli.app, ["serve", "--key-file", str(keyfile(tmp_path))]
    )

    assert result.exit_code == 0
    assert db_path.exists()


def test_serve_and_reset_document_the_db_flag() -> None:
    for command in ("serve", "reset"):
        out = CliRunner().invoke(cli.app, [command, "--help"]).output
        assert "--db" in out
        assert ENV_DB in out


def test_reset_db_flag_wipes_the_named_database(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv(ENV_DB, raising=False)
    db_path = tmp_path / "data" / ".hrono" / "hrono.db"
    db_path.parent.mkdir(parents=True)
    open_database(db_path).close()
    clone = db_path.parent / "cache" / "sources" / "repo"
    clone.mkdir(parents=True)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    result = CliRunner().invoke(
        cli.app, ["reset", "--force", "--db", str(db_path)]
    )

    assert result.exit_code == 0
    assert not db_path.exists()
    assert not clone.exists()
