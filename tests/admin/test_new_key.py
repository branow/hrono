"""A new install can make its master key and be told how to use it.

`hrono serve` needs a master key, so hrono must generate one and say how to
pass it; without that the first step of the first session is a wall.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from typer.testing import CliRunner

from hrono import cli
from hrono.crypto.masterkey import KeyNotProvided

runner = CliRunner()


def test_the_key_it_writes_is_a_usable_fernet_key(tmp_path: Path) -> None:
    out = tmp_path / "hrono.key"

    result = runner.invoke(cli.app, ["admin", "new-key", "--out", str(out)])

    assert result.exit_code == 0
    # the real thing: it round-trips a secret, not just "looks like base64"
    cipher = Fernet(out.read_bytes())
    assert cipher.decrypt(cipher.encrypt(b"a provider secret")) == (
        b"a provider secret"
    )


def test_the_key_file_is_readable_only_by_its_owner(tmp_path: Path) -> None:
    out = tmp_path / "hrono.key"

    runner.invoke(cli.app, ["admin", "new-key", "--out", str(out)])

    assert stat.S_IMODE(out.stat().st_mode) == 0o600


def test_it_refuses_to_overwrite_an_existing_key(tmp_path: Path) -> None:
    """Replacing the key a database was encrypted under destroys every secret
    in it, so this one is a refusal rather than a prompt."""
    out = tmp_path / "hrono.key"
    runner.invoke(cli.app, ["admin", "new-key", "--out", str(out)])
    first = out.read_bytes()

    result = runner.invoke(cli.app, ["admin", "new-key", "--out", str(out)])

    assert result.exit_code == 1
    assert out.read_bytes() == first
    assert "already exists" in result.output


def test_without_out_it_prints_a_key(tmp_path: Path) -> None:
    result = runner.invoke(cli.app, ["admin", "new-key"])

    assert result.exit_code == 0
    Fernet(result.output.strip().encode())  # raises if it is not one


def test_two_keys_are_different(tmp_path: Path) -> None:
    # a "generator" that returns a constant would pass every test above
    one = runner.invoke(cli.app, ["admin", "new-key"]).output.strip()
    two = runner.invoke(cli.app, ["admin", "new-key"]).output.strip()

    assert one != two


def test_the_missing_key_error_names_the_command_that_makes_one() -> None:
    """The message is the only documentation a stuck user has in front of
    them, so the command it names has to be one that exists."""
    message = str(KeyNotProvided())

    assert "hrono admin new-key" in message
    assert "hrono serve --key-file" in message
    assert "HRONO_MASTER_KEY" in message


def test_the_command_the_error_names_is_really_there() -> None:
    # naming a command that does not exist would be worse than saying nothing
    result = runner.invoke(cli.app, ["admin", "new-key", "--help"])

    assert result.exit_code == 0


@pytest.mark.parametrize("flag", ["--help"])
def test_the_key_file_option_explains_itself(flag: str) -> None:
    result = runner.invoke(cli.app, ["serve", flag])

    assert "master key" in result.output.lower()
