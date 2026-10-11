import pytest
from cryptography.fernet import Fernet

from hrono.crypto.cipher import (
    Cipher,
    InvalidCiphertext,
    KeyMismatch,
)

KEY = Fernet.generate_key()


def cipher(key_id: int = 1, key: bytes = KEY) -> Cipher:
    return Cipher.from_key(key, key_id)


@pytest.mark.parametrize(
    "plaintext",
    ["", "simple", "héllo 🌟 secret", "line\nbreak\ttab", "x" * 10_000],
)
def test_round_trips_arbitrary_utf8(plaintext: str) -> None:
    box = cipher()
    secret = box.encrypt(plaintext)
    assert box.decrypt(secret.key_id, secret.ciphertext) == plaintext


def test_encrypt_tags_the_active_key_id() -> None:
    secret = cipher(key_id=7).encrypt("value")
    assert secret.key_id == 7


def test_decrypt_with_mismatched_key_id_raises() -> None:
    box = cipher(key_id=1)
    secret = box.encrypt("value")
    with pytest.raises(KeyMismatch):
        box.decrypt(2, secret.ciphertext)


def test_tampered_ciphertext_raises() -> None:
    box = cipher()
    secret = box.encrypt("value")
    tampered = secret.ciphertext[:-4] + (
        "AAAA" if secret.ciphertext[-4:] != "AAAA" else "BBBB"
    )
    with pytest.raises(InvalidCiphertext):
        box.decrypt(secret.key_id, tampered)


def test_ciphertext_from_a_different_key_raises() -> None:
    other = cipher(key_id=1, key=Fernet.generate_key())
    token = other.encrypt("value").ciphertext
    with pytest.raises(InvalidCiphertext):
        cipher(key_id=1).decrypt(1, token)


def test_plaintext_is_not_present_in_ciphertext() -> None:
    secret = cipher().encrypt("supersecretvalue")
    assert "supersecretvalue" not in secret.ciphertext
