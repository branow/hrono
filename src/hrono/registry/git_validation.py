"""Reach + auth validation for git sources, run on write via the hook seam.

Uses ``git ls-remote`` (no clone, no content read) with a bounded timeout. The
credential is never placed in a reason, log line, or stored row: outcomes are
reported as opaque "cannot reach" / "authentication failed" reasons only.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from typing import TYPE_CHECKING

from hrono.registry.descriptor import ValidationFailed
from hrono.registry.git_auth import git_auth

if TYPE_CHECKING:
    from hrono.registry.descriptor import ValidationContext

_TIMEOUT = 10.0
_AUTH_MARKERS = (
    "authentication failed",
    "could not read username",
    "invalid username or password",
    "403",
    "permission denied",
    "access denied",
)

Runner = Callable[[str, dict[str, str] | None, float], tuple[int, str]]


def validate_git(
    config: dict[str, object],
    context: ValidationContext | None = None,
    *,
    run: Runner | None = None,
    timeout: float = _TIMEOUT,
) -> None:
    """Reject the write unless the git repo is reachable and auth works.

    ``context`` is unused here — git sources need only their own config.
    """
    probe = run if run is not None else _run
    auth = config["auth"]
    url = str(config["url"])

    with git_auth(url, auth) as (effective, env):  # type: ignore[arg-type]
        code, stderr = probe(effective, env, timeout)

    if code == 0:
        return
    if any(marker in stderr.lower() for marker in _AUTH_MARKERS):
        raise ValidationFailed("authentication failed")
    raise ValidationFailed("cannot reach repository")


def _run(
    url: str, env: dict[str, str] | None, timeout: float
) -> tuple[int, str]:
    environment = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    if env is not None:
        environment.update(env)
    try:
        completed = subprocess.run(
            ["git", "ls-remote", url],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=environment,
        )
    except subprocess.TimeoutExpired:
        return 124, "timed out"
    return completed.returncode, completed.stderr
