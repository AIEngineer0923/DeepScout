"""BYOK credential vault API. Secrets are never returned after storage."""

from __future__ import annotations

from uuid import uuid4

from deepscout_core.deployment import CredentialProvider, CredentialStatus
from deepscout_core.settings import Settings, get_settings
from deepscout_persistence.identity import (
    delete_credential,
    delete_principal_data,
    get_credential,
    list_credentials,
    record_event,
    revoke_all_sessions,
)
from deepscout_persistence.models import ProviderCredentialRow
from deepscout_research.credentials.vault import CredentialVault, VaultError, decode_master_key
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, SecretStr

from deepscout_api.access import load_access, require_user
from deepscout_api.deps import get_research_store

router = APIRouter(prefix="/api/v1/account", tags=["account"])

PRIVACY_COPY = (
    "Your provider credentials are encrypted at rest, are never displayed again after storage, "
    "are never sent back to the browser, and are decrypted only inside the trusted backend when "
    "required to call your selected provider. Your credentials are never used for another user's research. "
    "Provider charges are billed directly by the user's configured provider. DeepScout estimates may differ "
    "from provider invoices."
)


class CredentialWrite(BaseModel):
    secret: SecretStr = Field(min_length=8, max_length=4096)


def _vault(settings: Settings) -> CredentialVault:
    if settings.credential_encryption_key is None:
        raise HTTPException(status_code=503, detail="credential vault is not configured")
    try:
        return CredentialVault(decode_master_key(settings.credential_encryption_key.get_secret_value()))
    except VaultError as exc:
        raise HTTPException(status_code=503, detail="credential vault is not configured") from exc


def _meta(row: ProviderCredentialRow | None, provider: str) -> dict:
    if row is None:
        return {"provider": provider, "status": CredentialStatus.NOT_CONFIGURED.value, "configured": False}
    return {
        "provider": provider,
        "status": row.status,
        "configured": row.status == "configured",
        "key_version": row.key_version,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


@router.get("")
def account_profile(
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    rows = {row.provider: row for row in list_credentials(store._session, principal.id)}
    return {
        "id": str(principal.id),
        "display_name": principal.display_name,
        "email": principal.email if principal.email_verified else None,
        "privacy": PRIVACY_COPY,
        "credentials": [_meta(rows.get(item.value), item.value) for item in CredentialProvider],
        "credential_source": "USER_VAULT" if access.mode.value == "hosted" else "ENV",
    }


@router.put("/credentials/{provider}")
def put_credential(
    provider: str,
    body: CredentialWrite,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    if provider not in {item.value for item in CredentialProvider}:
        raise HTTPException(status_code=404, detail="unknown provider")
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    vault = _vault(settings)
    nonce, ciphertext, version = vault.encrypt(
        body.secret.get_secret_value().strip(),
        principal_id=principal.id,
        provider=provider,
    )
    row = get_credential(store._session, principal.id, provider)
    if row is None:
        row = ProviderCredentialRow(
            id=uuid4(),
            principal_id=principal.id,
            provider=provider,
            nonce=nonce,
            ciphertext=ciphertext,
            key_version=version,
            status="configured",
        )
        store._session.add(row)
        record_event(store._session, principal.id, "credential_add", provider)
    else:
        row.nonce = nonce
        row.ciphertext = ciphertext
        row.key_version = version
        row.status = "configured"
        record_event(store._session, principal.id, "credential_replace", provider)
    store._session.flush()
    return _meta(row, provider)


@router.delete("/credentials/{provider}", status_code=204)
def remove_credential(
    provider: str,
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> None:
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    if delete_credential(store._session, principal.id, provider):
        record_event(store._session, principal.id, "credential_delete", provider)


@router.get("/export")
def export_account(
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    runs, _ = store.list_runs(owner_principal_id=principal.id, limit=100, offset=0)
    templates = store.list_templates(owner_principal_id=principal.id)
    monitors = store.list_monitors(owner_principal_id=principal.id)
    rows = {row.provider: row for row in list_credentials(store._session, principal.id)}
    return {
        "principal": {
            "id": str(principal.id),
            "display_name": principal.display_name,
            "email": principal.email if principal.email_verified else None,
        },
        "runs": [
            {
                "id": str(row.id),
                "goal": row.goal,
                "status": row.status.value,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in runs
        ],
        "templates": [item.model_dump(mode="json") for item in templates],
        "monitors": [
            {"id": str(row.id), "name": row.name, "enabled": row.enabled} for row in monitors
        ],
        "credentials": [_meta(rows.get(item.value), item.value) for item in CredentialProvider],
    }


@router.post("/delete")
def delete_account(
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    if principal.kind != "user":
        raise HTTPException(status_code=400, detail="local operator cannot be deleted")
    record_event(store._session, principal.id, "account_delete")
    revoke_all_sessions(store._session, principal.id)
    delete_principal_data(store._session, principal.id)
    return {"deleted": True}
