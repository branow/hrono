"""The ``sync`` ingest op: pull a git source into a cache and pin its version.

First run clones into ``./.hrono/cache/sources/<name>``; later runs fetch and
hard-reset to the remote's current bytes. The synced version is the resolved
commit SHA — content-addressed, so it is the same whether the repo was fetched
over SSH or HTTPS (fetch-method-independent identity per the design sketch).
Registers into the op registry so the worker dispatches ``sync`` per source.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.registry import store as registry_store
from hrono.registry.git_auth import git_auth

_TIMEOUT = 120.0
_CACHE_ROOT = Path(".hrono/cache/sources")


class SyncError(Exception):
    """A source could not be synced (reason is credential-free)."""


def sync(job: Job, context: JobContext) -> None:
    """Clone/pull the job's source and record its commit as the version."""
    name = str(job.scope["name"])
    config = _load_source(context, name)
    version = _sync_repo(name, str(config["url"]), config["auth"], _TIMEOUT)
    _record_version(context, name, version)


def _load_source(context: JobContext, name: str) -> dict[str, object]:
    with context.database.connect() as conn:
        row = registry_store.get(conn, "sources", name)
    if row is None:
        raise SyncError(f"unknown source: {name}")
    config: dict[str, object] = json.loads(row["config"])
    auth = config.get("auth")
    key_id = row["key_id"]
    if isinstance(auth, dict) and key_id is not None and context.cipher:
        for field in ("token", "key"):
            if auth.get(field):
                auth[field] = context.cipher.decrypt(key_id, str(auth[field]))
    return config


def _sync_repo(name: str, url: str, auth: object, timeout: float) -> str:
    cache = _CACHE_ROOT / name
    auth_dict = auth if isinstance(auth, dict) else {"method": "none"}
    with git_auth(url, auth_dict) as (clean_url, env, config_args):
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
            env={**os.environ, **env},
        )
    except subprocess.TimeoutExpired as exc:
        raise SyncError(f"sync timed out for source: {name}") from exc
    if completed.returncode != 0:
        raise SyncError(f"sync failed for source: {name}")
    return completed.stdout


def _record_version(context: JobContext, name: str, version: str) -> None:
    now = datetime.now(UTC).isoformat()
    with context.database.connect() as conn, conn:
        conn.execute(
            "INSERT INTO source_state (source, version, synced_at) "
            "VALUES (?, ?, ?) ON CONFLICT(source) DO UPDATE SET "
            "version = excluded.version, synced_at = excluded.synced_at",
            (name, version, now),
        )


OPS["sync"] = sync
