from hrono.crypto.keys import fingerprint


def test_fingerprint_is_a_stable_sha256_hex() -> None:
    digest = fingerprint(b"master-key")
    assert fingerprint(b"master-key") == digest
    assert fingerprint(b"key-a") != fingerprint(b"key-b")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


def test_fingerprint_does_not_reveal_key() -> None:
    key = b"super-secret-master-key"
    digest = fingerprint(key)
    assert key.hex() not in digest
    assert key.decode() not in digest
