"""Provider reachability + auth validation for connections, run on write.

Dispatch is data-driven: one validator per provider, so a new provider is a map
entry (T44), not a branch. ``anthropic`` hits the no-inference list-models
endpoint (200 = the key authenticates). ``claude-code`` has no credential at all
— it bills through the operator's login — so what it validates is that the CLI
is present and runnable, which is the failure a user would otherwise meet hours
later at ``condense`` time (#107). Other providers keep the no-op stub until
their tickets. The api-key never appears in a reason or log line.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from typing import TYPE_CHECKING

import httpx

from hrono.registry.descriptor import ValidationFailed

if TYPE_CHECKING:
    from hrono.registry.descriptor import ValidationContext

_TIMEOUT = 10.0
_CLI_TIMEOUT = 15.0
_DEFAULT_ENDPOINT = "https://api.anthropic.com"

Runner = Callable[[str, str, float], int]
Probe = Callable[[], bool]


def validate_connection(
    config: dict[str, object],
    context: ValidationContext | None = None,
    *,
    run: Runner | None = None,
    probe: Probe | None = None,
    timeout: float = _TIMEOUT,
) -> None:
    """Reject the write unless the provider validates the credential.

    ``context`` is unused here — a connection validates against its own key.
    """
    provider = str(config["provider"])
    if provider == "claude-code":  # no credential; the CLI is the credential
        _validate_claude_code(probe if probe is not None else _cli_version)
        return
    validator = _VALIDATORS.get(provider)
    if validator is None:
        return
    validator(config, run if run is not None else _get, timeout)


def _validate_anthropic(
    config: dict[str, object], run: Runner, timeout: float
) -> None:
    key = str(config["auth"]["key"])  # type: ignore[index]
    endpoint = config.get("endpoint") or _DEFAULT_ENDPOINT
    url = str(endpoint).rstrip("/") + "/v1/models"
    status = run(url, key, timeout)
    if status == 200:
        return
    if status in (401, 403):
        raise ValidationFailed("authentication failed")
    raise ValidationFailed("cannot reach provider")


def _validate_claude_code(probe: Probe) -> None:
    """A ``claude-code`` connection is valid when the CLI answers (#107).

    There is no key to check — it bills through the operator's own login — so
    what must be true at WRITE time is that the binary is present and runnable.
    Otherwise the failure surfaces at ``condense`` time, hours later, as a
    subprocess error on a job the user has already paid to reach.
    """
    if not probe():
        raise ValidationFailed(
            "the claude CLI is not on PATH or is not runnable"
        )


def _cli_version() -> bool:
    try:
        done = subprocess.run(  # noqa: S603 - a fixed argv, no user input
            ["claude", "--version"],  # noqa: S607
            capture_output=True,
            timeout=_CLI_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def _get(url: str, api_key: str, timeout: float) -> int:
    try:
        response = httpx.get(
            url,
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
            timeout=timeout,
        )
    except httpx.HTTPError:
        return 0
    return response.status_code


_VALIDATORS: dict[str, Callable[..., None]] = {
    "anthropic": _validate_anthropic,
}
