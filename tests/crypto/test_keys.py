import dataclasses

import pytest

from hrono.crypto.keys import KeyRecord, fingerprint


def test_fingerprint_is_deterministic() -> None:
    assert fingerprint(b"master-key") == fingerprint(b"master-key")


def test_fingerprint_differs_for_different_keys() -> None:
    assert fingerprint(b"key-a") != fingerprint(b"key-b")


def test_fingerprint_is_sha256_hex() -> None:
    digest = fingerprint(b"master-key")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_fingerprint_does_not_reveal_key() -> None:
    key = b"super-secret-master-key"
    digest = fingerprint(key)
    assert key.hex() not in digest
    assert key.decode() not in digest


def test_key_record_is_frozen() -> None:
    record = KeyRecord(key_id=1, fingerprint="abc", created_at="2026-08-15")
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.key_id = 2  # type: ignore[misc]
