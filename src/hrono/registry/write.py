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


def decrypt(
    config: dict[str, object],
    descriptor: Descriptor,
    cipher: Cipher,
    key_id: int,
) -> dict[str, object]:
    """Return the config with its declared secrets decrypted in place.

    The inverse of ``encrypt``, and reading the SAME ``secret_paths``: a source
    type whose credential sits somewhere other than ``auth.token`` is then
    decrypted by declaring that path, not by editing the reader that needs it.
    """
    plain = deepcopy(config)
    for path in descriptor.secret_paths:
        holder = _holder(plain, path)
        if holder is None:
            continue
        parent, key = holder
        if parent[key] is None:
            continue
        parent[key] = cipher.decrypt(key_id, str(parent[key]))
    return plain


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


def unmask(
    config: dict[str, object],
    previous: dict[str, object],
    descriptor: Descriptor,
) -> dict[str, object]:
    """Return ``config`` with every still-masked secret taken from ``previous``.

    The inverse of the trap an edit FORM sets: the page can only ever show a
    secret as ``***``, so a form that posts back what it displayed writes the
    mask over the credential and the source stops authenticating — with the
    config looking exactly right. A field left at the mask means UNTOUCHED, and
    untouched is the value already stored.

    Reading the same ``secret_paths`` as ``mask`` and ``encrypt``, so a
    collection whose credential moves is covered by declaring the new path,
    not by remembering this function exists.
    """
    merged = deepcopy(config)
    for path in descriptor.secret_paths:
        holder = _holder(merged, path)
        if holder is None:
            continue
        parent, key = holder
        if parent[key] != MASK:
            continue
        before = _holder(previous, path)
        if before is None:
            continue
        parent[key] = before[0][before[1]]
    return merged


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
