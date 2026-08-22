"""Copy maintainer env API keys into the operator's BYOK vault (hosted only)."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID

from deepscout_core.deployment import CredentialProvider
from deepscout_core.settings import Settings
from deepscout_persistence.identity import get_auth_provider_account_id
from pydantic import SecretStr
from sqlalchemy.orm import Session

from deepscout_research.credentials.vault_store import (
    VaultNotConfiguredError,
    secret_value,
    upsert_vault_credential,
)

_PROVIDER_ENV_GETTERS: dict[str, Callable[[Settings], SecretStr | None]] = {
    CredentialProvider.GOOGLE.value: lambda settings: settings.google_api_key,
    CredentialProvider.OPENAI.value: lambda settings: settings.openai_api_key,
    CredentialProvider.ANTHROPIC.value: lambda settings: settings.anthropic_api_key,
    CredentialProvider.TAVILY.value: lambda settings: settings.tavily_api_key,
    CredentialProvider.LANGSMITH.value: lambda settings: settings.langsmith_api_key,
}


def is_operator_github_account(
    settings: Settings,
    *,
    provider: str,
    provider_account_id: str,
) -> bool:
    maintainer_id = (settings.maintainer_vault_github_id or "").strip()
    if not maintainer_id or not settings.is_hosted():
        return False
    return provider == "github" and provider_account_id == maintainer_id


def is_operator_principal(session: Session, principal_id: UUID, settings: Settings) -> bool:
    maintainer_id = (settings.maintainer_vault_github_id or "").strip()
    if not maintainer_id or not settings.is_hosted():
        return False
    github_id = get_auth_provider_account_id(session, principal_id, "github")
    return github_id == maintainer_id


def sync_operator_vault_from_env(
    session: Session,
    principal_id: UUID,
    settings: Settings,
) -> list[str]:
    """Upsert maintainer env keys into the operator vault. Returns synced provider names."""
    if not is_operator_principal(session, principal_id, settings):
        return []
    synced: list[str] = []
    for provider, getter in _PROVIDER_ENV_GETTERS.items():
        value = secret_value(getter(settings))
        if value is None:
            continue
        try:
            upsert_vault_credential(
                session,
                principal_id=principal_id,
                provider=provider,
                secret=value,
                settings=settings,
                event_type="credential_operator_sync",
            )
        except VaultNotConfiguredError:
            return synced
        synced.append(provider)
    return synced


def try_sync_operator_vault(
    session: Session,
    principal_id: UUID,
    settings: Settings,
) -> list[str]:
    """No-op unless principal matches MAINTAINER_VAULT_GITHUB_ID."""
    return sync_operator_vault_from_env(session, principal_id, settings)
