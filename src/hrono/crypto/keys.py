"""Master-key identity: the in-code key model and its fingerprint.

A ``KeyRecord`` mirrors one row of the ``keys`` registry. The registry stores
only fingerprints, never key material, so a wrong or rotated key surfaces as a
clear per-record mismatch rather than a silent decryption failure.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class KeyRecord:
    key_id: int
    fingerprint: str
    created_at: str


def fingerprint(key: bytes) -> str:
    """Return the SHA-256 hex digest of the raw master-key bytes.

    Deterministic and non-reversible: safe to persist as an identity for the
    key without exposing the key itself.
    """
    return hashlib.sha256(key).hexdigest()
