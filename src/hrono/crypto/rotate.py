"""Rotating the master key.

Every provider secret is encrypted under one key and tagged with its ``key_id``.
Changing that key means decrypting each row under the old one and re-encrypting
it under the new, in ONE transaction: the server holds a single cipher, so a row
left on the other key raises ``KeyMismatch`` and is unreadable by either side. A
half-rotated database is worse than an unrotated one.

The old key is PROOF OF POSSESSION, checked against the stored fingerprint
before anything is written. Without it, whoever reaches the admin endpoint can
re-encrypt the corpus under a key of their own choosing and lock the owner out.

**Neither key is ever written anywhere.** Not to the jobs table, not to a log,
not into an error. That is why this runs synchronously rather than as the queued
job the spec describes: a job's ``scope`` is persisted, and the inputs here are
two master keys.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime

from cryptography.fernet import Fernet

from hrono.crypto.cipher import Cipher
from hrono.crypto.keys import fingerprint
from hrono.db.database import tx
from hrono.errors import BadRequest, Forbidden
from hrono.registry import store
from hrono.registry.collections import COLLECTIONS
from hrono.registry.write import decrypt, encrypt


class WrongOldKey(Forbidden):
    """The old key does not match the one this database was encrypted with."""

    def __init__(self) -> None:
        # no fingerprints, no key material: a mismatch says only that it is one
        super().__init__("the old key does not match this database's key")


class UnusableNewKey(BadRequest):
    """The new key is not a valid Fernet key."""

    def __init__(self) -> None:
        super().__init__("the new key is not a valid encryption key")


@dataclass(frozen=True)
class Rotation:
    """What the rotation changed."""

    key_id: int
    rows: int


def rotate(
    conn: sqlite3.Connection, old_key: bytes, new_key: bytes
) -> Rotation:
    """Re-encrypt every secret under ``new_key``; return the new key_id.

    All or nothing. The whole walk is inside one ``with conn``, so a row that
    fails to decrypt — a database already half-touched by something else, a
    corrupted token — rolls the transaction back and leaves every row on the
    old key, which is the state the operator's key file still describes.
    """
    _require_old_key(conn, old_key)
    try:
        new_fernet = Fernet(new_key)
    except (ValueError, TypeError) as exc:
        raise UnusableNewKey from exc

    with tx(conn):
        cursor = conn.execute(
            "INSERT INTO keys (key_hash, created_at) VALUES (?, ?)",
            (fingerprint(new_key), datetime.now(UTC).isoformat()),
        )
        new_id = int(cursor.lastrowid or 0)
        old_cipher = Cipher.from_key(old_key, _active_id(conn, old_key))
        new_cipher = Cipher(new_fernet, new_id)
        rows = sum(
            _rotate_collection(conn, descriptor, old_cipher, new_cipher)
            for descriptor in COLLECTIONS
        )
    return Rotation(key_id=new_id, rows=rows)


def _rotate_collection(
    conn: sqlite3.Connection,
    descriptor: object,
    old_cipher: Cipher,
    new_cipher: Cipher,
) -> int:
    """Re-encrypt one collection's secret-bearing rows; return how many."""
    if not descriptor.secret_paths:  # type: ignore[attr-defined]
        return 0  # a secretless collection has nothing tagged with a key_id
    moved = 0
    for row in store.list_all(conn, descriptor.collection):  # type: ignore[attr-defined]
        if row["key_id"] is None:
            continue  # no secret in this row: nothing is tagged, nothing moves
        plain = decrypt(
            json.loads(row["config"]),
            descriptor,  # type: ignore[arg-type]
            old_cipher,
            int(row["key_id"]),
        )
        stored, key_id = encrypt(plain, descriptor, new_cipher)  # type: ignore[arg-type]
        conn.execute(
            "UPDATE registry SET config = ?, key_id = ? "
            "WHERE collection = ? AND name = ?",
            (
                json.dumps(stored),
                key_id,
                descriptor.collection,  # type: ignore[attr-defined]
                row["name"],
            ),
        )
        moved += 1
    return moved


def _require_old_key(conn: sqlite3.Connection, old_key: bytes) -> None:
    row = conn.execute(
        "SELECT key_hash FROM keys ORDER BY key_id DESC LIMIT 1"
    ).fetchone()
    if row is None or row["key_hash"] != fingerprint(old_key):
        raise WrongOldKey


def _active_id(conn: sqlite3.Connection, old_key: bytes) -> int:
    row = conn.execute(
        "SELECT key_id FROM keys WHERE key_hash = ?", (fingerprint(old_key),)
    ).fetchone()
    return int(row["key_id"])
