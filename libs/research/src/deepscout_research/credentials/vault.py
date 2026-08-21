"""AEAD credential vault. Plaintext exists only for the duration of a provider call."""

from __future__ import annotations

import os
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from deepscout_core.deployment import CredentialProvider


class VaultError(ValueError):
    """Credential encryption/decryption failure."""


def decode_master_key(raw: str) -> bytes:
    key = raw.strip().encode("utf-8")
    if len(key) == 32:
        return key
    import base64

    try:
        decoded = base64.urlsafe_b64decode(raw.strip() + "==")
    except Exception as exc:
        raise VaultError("CREDENTIAL_ENCRYPTION_KEY is not valid") from exc
    if len(decoded) != 32:
        raise VaultError("CREDENTIAL_ENCRYPTION_KEY must decode to 32 bytes")
    return decoded


class CredentialVault:
    def __init__(self, master_key: bytes, *, key_version: int = 1) -> None:
        if len(master_key) != 32:
            raise VaultError("master key must be 32 bytes")
        self._aead = AESGCM(master_key)
        self._key_version = key_version

    def encrypt(
        self,
        plaintext: str,
        *,
        principal_id: UUID,
        provider: CredentialProvider | str,
    ) -> tuple[bytes, bytes, int]:
        nonce = os.urandom(12)
        provider_value = str(provider)
        associated = f"{principal_id}:{provider_value}:v{self._key_version}".encode()
        ciphertext = self._aead.encrypt(nonce, plaintext.encode("utf-8"), associated)
        return nonce, ciphertext, self._key_version

    def decrypt(
        self,
        *,
        nonce: bytes,
        ciphertext: bytes,
        principal_id: UUID,
        provider: CredentialProvider | str,
        key_version: int,
    ) -> str:
        associated = f"{principal_id}:{provider}:v{key_version}".encode()
        try:
            return self._aead.decrypt(nonce, ciphertext, associated).decode("utf-8")
        except Exception as exc:
            raise VaultError("credential decrypt failed") from exc
