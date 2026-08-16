"""Shared write helpers: secret encryption, masking, and the content hash.

Used by the engine (on every write) and by default seeding, so both encrypt,
mask, and hash a config identically.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy

from hrono.crypto.cipher import Cipher
from hrono.registry.descriptor import Descriptor

MASK = "***"


def encrypt(
    config: dict[str, object], descriptor: Descriptor, cipher: Cipher
) -> tuple[dict[str, object], int | None]:
    """Return the config with secrets encrypted, plus the tagging key_id."""
    stored = deepcopy(config)
    key_id: int | None = None
    for path in descriptor.secret_paths:
        holder = _holder(stored, path)
        if holder is None:
            continue
        parent, key = holder
        if parent[key] is None:
            continue
        secret = cipher.encrypt(str(parent[key]))
        parent[key] = secret.ciphertext
        key_id = secret.key_id
    return stored, key_id


def mask(
    config: dict[str, object], descriptor: Descriptor
) -> dict[str, object]:
    """Return the config with secret fields replaced by the mask."""
    masked = deepcopy(config)
    for path in descriptor.secret_paths:
        holder = _holder(masked, path)
        if holder is None:
            continue
        parent, key = holder
        if parent[key] is not None:
            parent[key] = MASK
    return masked


def content_hash(body: str) -> str:
    """Return the SHA-256 hex digest of a stored config body."""
    return hashlib.sha256(body.encode()).hexdigest()


def _holder(
    data: dict[str, object], path: tuple[str, ...]
) -> tuple[dict[str, object], str] | None:
    node: object = data
    for key in path[:-1]:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    if not isinstance(node, dict) or path[-1] not in node:
        return None
    return node, path[-1]
