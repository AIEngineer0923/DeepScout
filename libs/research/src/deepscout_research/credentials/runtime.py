"""Hosted run settings use only the owner's vault. Maintainer env keys are never copied."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
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


_LANGSMITH_ENV_KEYS = (
    "LANGSMITH_TRACING",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
    "LANGSMITH_WORKSPACE_ID",
    "LANGSMITH_ENDPOINT",
    "LANGCHAIN_TRACING_V2",
    "LANGCHAIN_API_KEY",
)


def _apply_observability_environment(settings: Settings, *, hosted_baseline: bool = False) -> None:
    tracing = (
        not hosted_baseline
        and settings.langsmith_tracing
        and settings.langsmith_api_key is not None
    )
    values = {
        "LANGSMITH_TRACING": "true" if tracing else "false",
        "LANGSMITH_API_KEY": (
            settings.langsmith_api_key.get_secret_value() if tracing else None
        ),
        "LANGSMITH_PROJECT": settings.langsmith_project if tracing else None,
        "LANGSMITH_WORKSPACE_ID": settings.langsmith_workspace_id if tracing else None,
        "LANGSMITH_ENDPOINT": settings.langsmith_endpoint if tracing else None,
        "LANGCHAIN_TRACING_V2": None,
        "LANGCHAIN_API_KEY": None,
    }
    for key, value in values.items():
        if value:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)


def configure_process_observability(settings: Settings) -> None:
    """Keep hosted processes free of operator tracing credentials between tenant runs."""
    _apply_observability_environment(settings, hosted_baseline=settings.is_hosted())


@contextmanager
def run_observability_environment(settings: Settings) -> Iterator[None]:
    """Install one run's tracing credentials and restore the process baseline afterwards."""
    previous = {key: os.environ.get(key) for key in _LANGSMITH_ENV_KEYS}
    _apply_observability_environment(settings)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


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
