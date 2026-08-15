"""Symmetric cipher for secrets at rest: Fernet keyed by the master key.

Every ciphertext is tagged with the ``key_id`` that produced it, so a wrong or
rotated key surfaces as a clear per-record error instead of silent garbage.
"""

from __future__ import annotations

from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken


class DecryptError(Exception):
    """A ciphertext could not be decrypted with the active key."""


class KeyMismatch(DecryptError):
    """The ciphertext was written under a different key than the active one."""

    def __init__(self, active_key_id: int, ciphertext_key_id: int) -> None:
        super().__init__("ciphertext key_id does not match the active key")
        self.active_key_id = active_key_id
        self.ciphertext_key_id = ciphertext_key_id


class InvalidCiphertext(DecryptError):
    """The token is malformed or has been tampered with."""


@dataclass(frozen=True)
class Secret:
    key_id: int
    ciphertext: str


class Cipher:
    """Encrypts and decrypts secrets under one active key, tagging its key_id.

    Constructed by injection (a ``Fernet`` and the active ``key_id``) so it is
    unit-testable without a server and swappable when the key rotates.
    """

    def __init__(self, fernet: Fernet, key_id: int) -> None:
        self._fernet = fernet
        self._key_id = key_id

    @classmethod
    def from_key(cls, key: bytes, key_id: int) -> Cipher:
        """Build a cipher from raw Fernet key bytes and the active key_id."""
        return cls(Fernet(key), key_id)

    def encrypt(self, plaintext: str) -> Secret:
        """Encrypt ``plaintext``, tagging the result with the active key_id."""
        token = self._fernet.encrypt(plaintext.encode()).decode()
        return Secret(self._key_id, token)

    def decrypt(self, key_id: int, ciphertext: str) -> str:
        """Decrypt ``ciphertext``; raise if the key_id or token is wrong.

        Raises ``KeyMismatch`` when ``key_id`` is not the active key, and
        ``InvalidCiphertext`` when the token is malformed or tampered.
        """
        if key_id != self._key_id:
            raise KeyMismatch(self._key_id, key_id)
        try:
            return self._fernet.decrypt(ciphertext.encode()).decode()
        except InvalidToken as exc:
            raise InvalidCiphertext from exc
