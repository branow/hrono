import hashlib

import pytest

from hrono.crypto import tokens
from hrono.crypto.tokens import generate_token, hash_token, verify_token


def test_generate_token_is_distinct_and_high_entropy() -> None:
    minted = {generate_token() for _ in range(100)}
    assert len(minted) == 100
    assert all(len(token) >= 32 for token in minted)


def test_hash_token_is_deterministic_sha256_hex() -> None:
    token = "a-known-token"
    assert hash_token(token) == hash_token(token)
    assert hash_token(token) == hashlib.sha256(token.encode()).hexdigest()
    assert len(hash_token(token)) == 64


def test_hash_token_never_returns_the_input() -> None:
    token = generate_token()
    assert hash_token(token) != token


def test_verify_token_true_only_for_the_matching_token() -> None:
    token = generate_token()
    digest = hash_token(token)
    assert verify_token(token, digest) is True
    assert verify_token("wrong-token", digest) is False


def test_verify_token_uses_constant_time_compare(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    real = tokens.hmac.compare_digest

    def spy(left: str, right: str) -> bool:
        calls.append((left, right))
        return real(left, right)

    monkeypatch.setattr(tokens.hmac, "compare_digest", spy)
    token = generate_token()
    verify_token(token, hash_token(token))
    assert calls
