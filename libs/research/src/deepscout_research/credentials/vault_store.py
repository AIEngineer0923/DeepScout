"""Shared BYOK vault upsert helpers."""

from __future__ import annotations

from uuid import UUID, uuid4

from deepscout_core.settings import Settings
from deepscout_persistence.identity import get_credential, record_event
from deepscout_persistence.models import ProviderCredentialRow
from pydantic import SecretStr
from sqlalchemy.orm import Session

from deepscout_research.credentials.vault import CredentialVault, VaultError, decode_master_key


class VaultNotConfiguredError(RuntimeError):
    """Credential encryption is unavailable."""


def vault_from_settings(settings: Settings) -> CredentialVault:
    if settings.credential_encryption_key is None:
        raise VaultNotConfiguredError("credential vault is not configured")
    return CredentialVault(decode_master_key(settings.credential_encryption_key.get_secret_value()))


def upsert_vault_credential(
    session: Session,
    *,
    principal_id: UUID,
    provider: str,
    secret: str,
    settings: Settings,
    event_type: str,
) -> ProviderCredentialRow:
    cleaned = secret.strip()
    if len(cleaned) < 8:
        raise ValueError("credential secret is too short")
    try:
        vault = vault_from_settings(settings)
    except VaultError as exc:
        raise VaultNotConfiguredError("credential vault is not configured") from exc
    nonce, ciphertext, version = vault.encrypt(
        cleaned,
        principal_id=principal_id,
        provider=provider,
    )
    row = get_credential(session, principal_id, provider)
    if row is None:
        row = ProviderCredentialRow(
            id=uuid4(),
            principal_id=principal_id,
            provider=provider,
            nonce=nonce,
            ciphertext=ciphertext,
            key_version=version,
            status="configured",
        )
        session.add(row)
    else:
        row.nonce = nonce
        row.ciphertext = ciphertext
        row.key_version = version
        row.status = "configured"
    record_event(session, principal_id, event_type, provider)
    session.flush()
    return row


def secret_value(secret: SecretStr | None) -> str | None:
    if secret is None:
        return None
    value = secret.get_secret_value().strip()
    return value or None
