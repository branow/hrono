"""T44.2: a `claude-code` connection validates against the CLI, not a key."""

from pathlib import Path

import pytest

from hrono.registry.connection_validation import (
    _cli_version,
    validate_connection,
)
from hrono.registry.descriptor import ValidationFailed

CONFIG: dict[str, object] = {
    "name": "cli",
    "provider": "claude-code",
    "auth": {"method": "none"},
}


def test_a_present_cli_validates() -> None:
    validate_connection(dict(CONFIG), probe=lambda: True)


def test_a_missing_cli_is_rejected_at_write_time() -> None:
    # #107: there is no key to check — it bills through the operator's own
    # login — so what must hold at WRITE time is that the binary runs. Without
    # this the failure surfaces hours later at condense time, on a job the user
    # has already paid to reach.
    with pytest.raises(ValidationFailed, match="claude CLI"):
        validate_connection(dict(CONFIG), probe=lambda: False)


def test_the_real_probe_reports_a_missing_binary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # #108: the probe seam proves the wiring and cannot prove the probe works.
    # This drives the REAL subprocess probe against an empty PATH — no CLI to
    # find, no cost, and the OSError path exercised for real.
    monkeypatch.setenv("PATH", str(tmp_path))

    assert _cli_version() is False


def test_the_real_probe_accepts_a_runnable_binary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    binary = tmp_path / "claude"
    binary.write_text("#!/bin/sh\necho 2.1.259\n")
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))

    assert _cli_version() is True


def test_a_failing_binary_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # present but not logged in: exits non-zero, and must not pass validation.
    binary = tmp_path / "claude"
    binary.write_text("#!/bin/sh\nexit 1\n")
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))

    with pytest.raises(ValidationFailed, match="claude CLI"):
        validate_connection(dict(CONFIG))
