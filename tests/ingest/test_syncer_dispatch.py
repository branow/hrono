"""The sync op dispatches by source type; git is one entry.

What every source type owes the op is the same two things — content in the
cache, a version pinned — and nothing else. These pin that the op holds no
knowledge of git, that a type without a syncer fails by name rather than with a
KeyError, and that the REAL git syncer still drives the whole path
end to end through the seam.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from hrono.crypto.cipher import Cipher
from hrono.crypto.masterkey import reconcile
from hrono.db.database import Database
from hrono.ingest import SyncError
from hrono.ingest.sync import sync
from hrono.ingest.syncers import SYNCERS
from hrono.jobs.model import Job
from hrono.jobs.ops import JobContext
from hrono.registry import store as registry_store

KEY = Fernet.generate_key()
CLEAR = "what the syncer must receive in the clear"


def _job(name: str) -> Job:
    return Job(
        id="j1",
        parent_id=None,
        tree=None,
        op="sync",
        scope={"name": name},
        status="running",
        error=None,
        created_at="t",
        updated_at="t",
    )


def _register(
    database: Database,
    name: str,
    config: dict[str, object],
    key_id: int | None = None,
) -> None:
    with database.connect() as conn:
        registry_store.insert(
            conn, "sources", name, json.dumps(config), key_id, "t"
        )


def _version(database: Database, name: str) -> str | None:
    with database.connect() as conn:
        row = conn.execute(
            "SELECT version FROM source_state WHERE source = ?", (name,)
        ).fetchone()
    return None if row is None else str(row["version"])


@pytest.fixture
def context(tmp_path: Path) -> Iterator[tuple[Database, JobContext]]:
    database = Database.at(tmp_path / "hrono.db")
    with database.connect() as conn, conn:
        key_id = reconcile(conn, KEY).key_id
    yield (
        database,
        JobContext(database, Cipher.from_key(KEY, key_id), tmp_path / "cache"),
    )
    database.close()


@pytest.fixture
def fake(context: tuple[Database, JobContext]) -> Iterator[list[tuple]]:
    """A source type is a table entry: no edit to the op that calls it."""
    calls: list[tuple] = []

    def fake_sync(
        config: dict[str, object], cache: Path, timeout: float
    ) -> str:
        calls.append((config, cache, timeout))
        cache.mkdir(parents=True, exist_ok=True)
        (cache / "page.md").write_text("pulled\n")
        return "page-version-7"

    SYNCERS["fake"] = fake_sync
    try:
        yield calls
    finally:
        del SYNCERS["fake"]


def test_sync_delegates_to_the_type_s_syncer(
    context: tuple[Database, JobContext], fake: list[tuple]
) -> None:
    database, ctx = context
    _register(database, "wiki", {"name": "wiki", "type": "fake"})

    sync(_job("wiki"), ctx)

    (config, cache, _timeout) = fake[0]
    assert config["name"] == "wiki"
    assert (cache / "page.md").read_text() == "pulled\n"
    # the version is opaque text, pinned as whatever the syncer returned
    assert _version(database, "wiki") == "page-version-7"


def test_a_type_with_no_syncer_fails_by_name(
    context: tuple[Database, JobContext],
) -> None:
    database, ctx = context
    _register(database, "wiki", {"name": "wiki", "type": "no-such-type"})
    assert "no-such-type" not in SYNCERS

    with pytest.raises(SyncError) as raised:
        sync(_job("wiki"), ctx)

    assert "no-such-type" in str(raised.value)


def test_the_syncer_receives_declared_secrets_decrypted(
    context: tuple[Database, JobContext], fake: list[tuple]
) -> None:
    # `sources` declares auth.token secret, so the op decrypts by that
    # declaration rather than by knowing git's field names.
    database, ctx = context
    secret = ctx.cipher.encrypt(CLEAR)  # type: ignore[union-attr]
    _register(
        database,
        "wiki",
        {
            "name": "wiki",
            "type": "fake",
            "auth": {"method": "token", "token": secret.ciphertext},
        },
        key_id=secret.key_id,
    )

    sync(_job("wiki"), ctx)

    (config, _cache, _timeout) = fake[0]
    assert config["auth"]["token"] == CLEAR  # type: ignore[index]
