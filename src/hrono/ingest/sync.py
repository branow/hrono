"""The ``sync`` ingest op: bring a source's content into the cache (T25).

The op itself knows nothing about how any source type is fetched: it resolves
the source's config, decrypts its secrets, and hands both to the syncer
registered for its ``type`` (#142). What comes back is the version, opaque
text, which it pins in ``source_state``.

Registers into the op registry so the worker dispatches ``sync`` per source.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime

from hrono.ingest import SyncError
from hrono.ingest.syncers import SYNCERS
from hrono.jobs.model import Job
from hrono.jobs.ops import OPS, JobContext
from hrono.registry import store as registry_store
from hrono.registry.collections.sources import SOURCES
from hrono.registry.write import decrypt

_TIMEOUT = 120.0

__all__ = ["SyncError", "sync", "sync_source"]


def sync(job: Job, context: JobContext) -> Mapping[str, int]:
    """Sync the job's source through its type's syncer and pin the version.

    Reports whether the version is new, so a first sync says it fetched one
    and a re-sync of an unchanged source says it had nothing to do (#213).
    """
    return sync_source(context, str(job.scope["name"]))


def sync_source(context: JobContext, name: str) -> Mapping[str, int]:
    """Bring one registered source into the cache and pin its version.

    The op's body, callable without a job: the setup path fetches a source to
    show what it holds, and must fetch it the way a sync does or the two would
    disagree about what the cache is.
    """
    config = _load_source(context, name)
    source_type = str(config["type"])
    syncer = SYNCERS.get(source_type)
    if syncer is None:
        raise SyncError(f"no syncer for source type: {source_type}")
    version = syncer(config, context.cache_for(name), _TIMEOUT)
    previous = _pinned_version(context, name)
    _record_version(context, name, version)
    return {"fetched": int(version != previous)}


def _load_source(context: JobContext, name: str) -> dict[str, object]:
    with context.database.connect() as conn:
        row = registry_store.get(conn, "sources", name)
    if row is None:
        raise SyncError(f"unknown source: {name}")
    config: dict[str, object] = json.loads(row["config"])
    key_id = row["key_id"]
    if key_id is None or context.cipher is None:
        return config
    return decrypt(config, SOURCES, context.cipher, int(key_id))


def _pinned_version(context: JobContext, name: str) -> str | None:
    with context.database.connect() as conn:
        row = conn.execute(
            "SELECT version FROM source_state WHERE source = ?", (name,)
        ).fetchone()
    return None if row is None else str(row["version"])


def _record_version(context: JobContext, name: str, version: str) -> None:
    now = datetime.now(UTC).isoformat()
    with context.database.write() as conn:
        conn.execute(
            "INSERT INTO source_state (source, version, synced_at) "
            "VALUES (?, ?, ?) ON CONFLICT(source) DO UPDATE SET "
            "version = excluded.version, synced_at = excluded.synced_at",
            (name, version, now),
        )


OPS["sync"] = sync
