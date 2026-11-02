"""Seed each collection's default rows on first run (seed-if-missing).

Idempotent like the bootstrap-admin flow: a default is inserted only when its
name is absent, so a restart adds nothing and a user-modified row is never
overwritten. The one exception is a default row that still holds an earlier
shipped version (``Descriptor.superseded``): it is untouched by the user, so
it moves to the current default. Seeded rows are marked ``is_default`` so
DELETE resets them.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime

from hrono.crypto.cipher import Cipher
from hrono.registry import store
from hrono.registry.descriptor import Descriptor
from hrono.registry.write import content_hash, encrypt


def seed_defaults(
    conn: sqlite3.Connection,
    cipher: Cipher,
    descriptors: Iterable[Descriptor],
) -> None:
    """Insert any missing default rows, marked as defaults."""
    now = datetime.now(UTC).isoformat()
    for descriptor in descriptors:
        for default in descriptor.defaults:
            name = str(default["name"])
            held = store.get(conn, descriptor.collection, name)
            stored, key_id = encrypt(dict(default), descriptor, cipher)
            payload = json.dumps(stored)
            if held is not None:
                if held["is_default"] and held["content_hash"] in (
                    descriptor.superseded.get(name, ())
                ):
                    store.replace(
                        conn,
                        descriptor.collection,
                        name,
                        payload,
                        key_id,
                        now,
                        content_hash(payload),
                    )
                continue
            store.insert(
                conn,
                descriptor.collection,
                name,
                payload,
                key_id,
                now,
                is_default=1,
                content_hash=content_hash(payload),
            )
