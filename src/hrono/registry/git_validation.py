"""Reach + auth validation for git sources, run on write via the hook seam.

Uses ``git ls-remote`` (no clone, no content read) with a bounded timeout. The
credential is never placed in a reason, log line, or stored row: outcomes are
reported as opaque "cannot reach" / "authentication failed" reasons only.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from collections.abc import Callable

from hrono.registry.descriptor import ValidationFailed

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
    *,
    run: Runner | None = None,
    timeout: float = _TIMEOUT,
) -> None:
    """Reject the write unless the git repo is reachable and auth works."""
    probe = run if run is not None else _run
    auth = config["auth"]
    method = auth["method"]  # type: ignore[index]
    url = str(config["url"])

    key_file: str | None = None
    env: dict[str, str] | None = None
    effective = url
    try:
        if method == "token":
            effective = _with_token(url, str(auth["token"]))  # type: ignore[index]
        elif method == "ssh":
            key_file = _write_key(str(auth["key"]))  # type: ignore[index]
            env = {
                "GIT_SSH_COMMAND": (
                    f"ssh -i {key_file} -o BatchMode=yes "
                    "-o StrictHostKeyChecking=no -o ConnectTimeout=10"
                )
            }
        code, stderr = probe(effective, env, timeout)
    finally:
        if key_file is not None:
            os.unlink(key_file)

    if code == 0:
        return
    if any(marker in stderr.lower() for marker in _AUTH_MARKERS):
        raise ValidationFailed("authentication failed")
    raise ValidationFailed("cannot reach repository")


def _with_token(url: str, token: str) -> str:
    prefix = "https://"
    if not url.startswith(prefix):
        return url
    rest = url[len(prefix) :]
    host = rest.split("/", 1)[0]
    user = "x-token-auth" if "bitbucket.org" in host else "x-access-token"
    return f"{prefix}{user}:{token}@{rest}"


def _write_key(key: str) -> str:
    descriptor, path = tempfile.mkstemp()
    with os.fdopen(descriptor, "w") as handle:
        handle.write(key if key.endswith("\n") else key + "\n")
    os.chmod(path, 0o600)
    return path


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
