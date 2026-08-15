"""Bearer-token primitives: generate, hash, and verify.

A token is high-entropy random, so a fast one-way hash with a constant-time
comparison is the correct and sufficient primitive; this is deliberately not a
password KDF (bcrypt/argon2), which exist for low-entropy secrets.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets


def generate_token() -> str:
    """Return a fresh high-entropy URL-safe token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of the token's UTF-8 bytes.

    Deterministic and one-way, mirroring ``keys.fingerprint`` in shape.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def verify_token(token: str, token_hash: str) -> bool:
    """Constant-time check that ``token`` hashes to ``token_hash``."""
    return hmac.compare_digest(hash_token(token), token_hash)
