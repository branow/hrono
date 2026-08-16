"""Resolve a git source's auth into an effective URL + env, once, for reuse.

Both validation (``git ls-remote``) and sync (``git clone``/``fetch``) inject
credentials the same way: token method rewrites the https URL, ssh writes a
0600 key file and points ``GIT_SSH_COMMAND`` at it (removed on exit). The
credential never lands in a reason, log, or stored row.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager


@contextmanager
def git_auth(
    url: str, auth: dict[str, object]
) -> Iterator[tuple[str, dict[str, str] | None]]:
    """Yield an (effective_url, env) pair carrying the source's auth."""
    method = auth.get("method")
    if method == "token":
        yield _with_token(url, str(auth["token"])), None
    elif method == "ssh":
        key_file = _write_key(str(auth["key"]))
        try:
            yield url, {"GIT_SSH_COMMAND": _ssh_command(key_file)}
        finally:
            os.unlink(key_file)
    else:
        yield url, None


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


def _ssh_command(key_file: str) -> str:
    return (
        f"ssh -i {key_file} -o BatchMode=yes "
        "-o StrictHostKeyChecking=no -o ConnectTimeout=10"
    )
