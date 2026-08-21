from uuid import uuid4

import pytest
from deepscout_core.deployment import CredentialProvider
from deepscout_research.credentials.vault import CredentialVault, VaultError


def test_round_trip_and_binding() -> None:
    vault = CredentialVault(b"0" * 32)
    principal = uuid4()
    nonce, ciphertext, version = vault.encrypt(
        "sk-test-not-a-real-key", principal_id=principal, provider=CredentialProvider.GOOGLE
    )
    assert (
        vault.decrypt(
            nonce=nonce,
            ciphertext=ciphertext,
            principal_id=principal,
            provider="google",
            key_version=version,
        )
        == "sk-test-not-a-real-key"
    )
    with pytest.raises(VaultError):
        vault.decrypt(
            nonce=nonce,
            ciphertext=ciphertext,
            principal_id=uuid4(),
            provider="google",
            key_version=version,
        )
