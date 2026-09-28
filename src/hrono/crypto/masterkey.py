"""Loading the master key at startup and reconciling it with the DB.

The raw key is read from a file or the environment, validated as a Fernet key,
and its fingerprint checked against the ``keys`` table so a wrong key is
rejected before any request is served. The raw key is never logged and never
stored; only its fingerprint reaches the database.
"""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet

from hrono.crypto.keys import KeyRecord, fingerprint
from hrono.errors import BadRequest


class MasterKeyError(BadRequest):
    """Base for master-key startup failures; the boundary maps it to output."""

    code = "master-key-error"


class KeyNotProvided(MasterKeyError):
    """Neither a key file nor the environment variable was given."""

    code = "master-key-missing"

    def __init__(self) -> None:
        super().__init__(
            "No master key provided.\n"
            "\n"
            "Every provider secret is encrypted under this key, so hrono will "
            "not start without it.\n"
            "Make one, then start the server with it:\n"
            "\n"
            "    hrono admin new-key --out hrono.key\n"
            "    hrono serve --key-file hrono.key\n"
            "\n"
            "Or put the key itself in HRONO_MASTER_KEY. Keep it safe: lose it "
            "and every stored secret is unreadable."
        )


class KeyFileUnreadable(MasterKeyError):
    """The key file does not exist or cannot be read."""

    code = "master-key-unreadable"

    def __init__(self, path: Path) -> None:
        super().__init__(f"Cannot read master key file: {path}")
        self.path = path


class InvalidKey(MasterKeyError):
    """The supplied bytes are not a valid Fernet key."""

    code = "master-key-invalid"

    def __init__(self) -> None:
        super().__init__(
            "Master key is not a valid Fernet key (expected a url-safe "
            "base64-encoded 32-byte key)."
        )


class WrongMasterKey(MasterKeyError):
    """The supplied key does not match the active key on record."""

    code = "wrong-master-key"

    def __init__(self, active_key_id: int) -> None:
        super().__init__("wrong master key: does not match the active key")
        self.active_key_id = active_key_id


def load_key(key_file: Path | None, env_value: str | None) -> bytes:
    """Resolve and validate the master key from a file or the environment.

    ``key_file`` wins when both are supplied. Returns the raw Fernet key bytes;
    raises a ``MasterKeyError`` subtype the caller maps to a startup failure.
    """
    if key_file is not None:
        try:
            raw = key_file.read_bytes().strip()
        except OSError as exc:
            raise KeyFileUnreadable(key_file) from exc
    elif env_value:
        raw = env_value.strip().encode()
    else:
        raise KeyNotProvided

    try:
        Fernet(raw)
    except (ValueError, TypeError) as exc:
        raise InvalidKey from exc
    return raw


def reconcile(conn: sqlite3.Connection, key: bytes) -> KeyRecord:
    """Match ``key`` against the ``keys`` table, recording it on first run.

    An empty table takes this key's fingerprint as the active key; an existing
    active key must match or startup is refused. Nothing is mutated on mismatch.
    """
    digest = fingerprint(key)
    row = conn.execute(
        "SELECT key_id, key_hash, created_at FROM keys "
        "ORDER BY key_id DESC LIMIT 1"
    ).fetchone()
    if row is not None:
        if row["key_hash"] != digest:
            raise WrongMasterKey(row["key_id"])
        return KeyRecord(row["key_id"], row["key_hash"], row["created_at"])

    created_at = datetime.now(UTC).isoformat()
    with conn:
        cursor = conn.execute(
            "INSERT INTO keys (key_hash, created_at) VALUES (?, ?)",
            (digest, created_at),
        )
    return KeyRecord(cursor.lastrowid or 0, digest, created_at)
