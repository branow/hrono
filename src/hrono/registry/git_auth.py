"""Authenticate git commands without persisting the secret to disk.

Both validation (``git ls-remote``) and sync (``git clone``/``fetch``) call
``git_auth`` and get back an (url, env, config_args) triple to splice into the
command. The URL is never rewritten to carry a token — token auth is supplied
through a transient inline credential helper that reads the token from the
environment, so nothing lands in ``.git/config`` or ``FETCH_HEAD``. SSH points
``GIT_SSH_COMMAND`` at a 0600 key file that is removed on exit.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager

_BASE_ENV = {"GIT_TERMINAL_PROMPT": "0"}


@contextmanager
def git_auth(
    url: str, auth: dict[str, object]
) -> Iterator[tuple[str, dict[str, str], list[str]]]:
    """Yield (url, env, config_args) that authenticate git for this source."""
    method = auth.get("method")
    if method == "token":
        env = {**_BASE_ENV, "HRONO_GIT_TOKEN": str(auth["token"])}
        yield url, env, _credential_args(_token_user(url))
    elif method == "ssh":
        key_file = _write_key(str(auth["key"]))
        try:
            yield (
                url,
                {**_BASE_ENV, "GIT_SSH_COMMAND": _ssh_command(key_file)},
                [],
            )
        finally:
            os.unlink(key_file)
    else:
        yield url, dict(_BASE_ENV), []


def _token_user(url: str) -> str:
    host = url.split("://", 1)[-1].split("/", 1)[0] if "://" in url else ""
    return "x-token-auth" if "bitbucket.org" in host else "x-access-token"


def _credential_args(user: str) -> list[str]:
    helper = (
        f"!f() {{ echo username={user}; echo password=$HRONO_GIT_TOKEN; }}; f"
    )
    return ["-c", "credential.helper=", "-c", f"credential.helper={helper}"]


def _write_key(key: str) -> str:
    descriptor, path = tempfile.mkstemp()
    with os.fdopen(descriptor, "w") as handle:
        handle.write(key if key.endswith("\n") else key + "\n")
    os.chmod(path, 0o600)
    return path


def _ssh_command(key_file: str) -> str:
    return (
        f"ssh -i {key_file} -o BatchMode=yes "
        "-o StrictHostKeyChecking=no -o ConnectTimeout=10"
    )
