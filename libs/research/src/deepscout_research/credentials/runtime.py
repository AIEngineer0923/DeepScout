"""Hosted run settings use only the owner's vault. Maintainer env keys are never copied."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.deployment import CredentialProvider, DeploymentMode
from deepscout_core.settings import Settings
from deepscout_persistence.models import ProviderCredentialRow
from deepscout_persistence.store import ResearchStore
from pydantic import SecretStr
from sqlalchemy import select

from deepscout_research.credentials.vault import CredentialVault, decode_master_key


class HostedCredentialError(RuntimeError):
    """User vault cannot satisfy a hosted provider call."""


def vault_from_settings(settings: Settings) -> CredentialVault | None:
    if settings.credential_encryption_key is None:
        return None
    return CredentialVault(decode_master_key(settings.credential_encryption_key.get_secret_value()))


def resolve_run_settings(store: ResearchStore, settings: Settings, run_id: UUID) -> Settings:
    if settings.deployment_mode == DeploymentMode.LOCAL:
        return settings
    row = store.get_run_row(run_id)
    if row is None or row.owner_principal_id is None:
        raise HostedCredentialError("hosted run is missing an owner")
    vault = vault_from_settings(settings)
    if vault is None:
        raise HostedCredentialError("credential vault is not configured")
    overlay: dict = {
        "google_api_key": None,
        "openai_api_key": None,
        "anthropic_api_key": None,
        "tavily_api_key": None,
        "langsmith_api_key": None,
        "langsmith_tracing": False,
    }
    records = store._session.scalars(
        select(ProviderCredentialRow).where(
            ProviderCredentialRow.principal_id == row.owner_principal_id,
            ProviderCredentialRow.status == "configured",
        )
    ).all()
    for record in records:
        secret = vault.decrypt(
            nonce=record.nonce,
            ciphertext=record.ciphertext,
            principal_id=record.principal_id,
            provider=record.provider,
            key_version=record.key_version,
        )
        wrapped = SecretStr(secret)
        if record.provider == CredentialProvider.GOOGLE:
            overlay["google_api_key"] = wrapped
        elif record.provider == CredentialProvider.OPENAI:
            overlay["openai_api_key"] = wrapped
        elif record.provider == CredentialProvider.ANTHROPIC:
            overlay["anthropic_api_key"] = wrapped
        elif record.provider == CredentialProvider.TAVILY:
            overlay["tavily_api_key"] = wrapped
        elif record.provider == CredentialProvider.LANGSMITH:
            overlay["langsmith_api_key"] = wrapped
            overlay["langsmith_tracing"] = True
    return settings.model_copy(update=overlay)
