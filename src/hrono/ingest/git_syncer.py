"""The git syncer: clone or pull a repo and pin its commit as the version.

First run clones into the cache path the caller chose — that root hangs off the
database file, never the working directory (#098); later runs fetch and hard-
reset to the remote's current bytes. The version is the resolved commit SHA —
content-addressed, so it is the same whether the repo was fetched over SSH or
HTTPS (fetch-method-independent identity, per the design sketch).

Moved out of the ``sync`` op unchanged (#142): clone/pull is git's transport,
not the abstraction every source type shares.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from hrono.ingest import SyncError
from hrono.registry.validation.git_auth import git_auth


def git_sync(config: dict[str, object], cache: Path, timeout: float) -> str:
    """Bring the repo at ``config['url']`` into ``cache``; return its SHA."""
    name = str(config["name"])
    auth = config.get("auth")
    auth_dict = auth if isinstance(auth, dict) else {"method": "none"}
    with git_auth(str(config["url"]), auth_dict) as (
        clean_url,
        env,
        config_args,
    ):
        if cache.exists():
            _run(["fetch", "origin"], name, cache, env, config_args, timeout)
            _run(
                ["reset", "--hard", "FETCH_HEAD"],
                name,
                cache,
                env,
                config_args,
                timeout,
            )
        else:
            cache.parent.mkdir(parents=True, exist_ok=True)
            try:
                _run(
                    ["clone", clean_url, str(cache)],
                    name,
                    None,
                    env,
                    config_args,
                    timeout,
                )
            except SyncError:
                shutil.rmtree(cache, ignore_errors=True)
                raise
        return _run(
            ["rev-parse", "HEAD"], name, cache, env, config_args, timeout
        ).strip()


def _run(
    args: list[str],
    name: str,
    cwd: Path | None,
    env: dict[str, str],
    config_args: list[str],
    timeout: float,
) -> str:
    prefix = ["-C", str(cwd)] if cwd is not None else []
    command = ["git", *prefix, *config_args, *args]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise SyncError(f"sync timed out for source: {name}") from exc
    if completed.returncode != 0:
        raise SyncError(f"sync failed for source: {name}")
    return completed.stdout
