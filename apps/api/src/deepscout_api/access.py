"""Server-side access context. Frontend hiding is never authorization."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from deepscout_core.deployment import LOCAL_SYSTEM_PRINCIPAL_ID, DeploymentMode
from deepscout_core.settings import Settings
from deepscout_persistence.identity import get_local_system, resolve_session
from deepscout_persistence.models import PrincipalRow, ResearchRunRow, ResearchTemplateRow
from deepscout_persistence.store import ResearchStore
from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

SESSION_COOKIE = "ds_session"


@dataclass(frozen=True)
class AccessContext:
    mode: DeploymentMode
    principal: PrincipalRow | None
    hosted_auth_ready: bool

    @property
    def principal_id(self) -> UUID | None:
        return None if self.principal is None else self.principal.id

    @property
    def is_local(self) -> bool:
        return self.mode == DeploymentMode.LOCAL


def load_access(request: Request, session: Session, settings: Settings) -> AccessContext:
    if not settings.is_hosted():
        return AccessContext(
            mode=DeploymentMode.LOCAL,
            principal=get_local_system(session),
            hosted_auth_ready=True,
        )
    token = request.cookies.get(SESSION_COOKIE)
    principal = resolve_session(session, token) if token else None
    return AccessContext(
        mode=DeploymentMode.HOSTED,
        principal=principal,
        hosted_auth_ready=settings.hosted_auth_ready(),
    )


def require_hosted_auth_config(access: AccessContext) -> None:
    if access.mode == DeploymentMode.HOSTED and not access.hosted_auth_ready:
        raise HTTPException(status_code=503, detail="Hosted authentication is not configured")


def require_user(access: AccessContext) -> PrincipalRow:
    require_hosted_auth_config(access)
    if access.is_local:
        assert access.principal is not None
        return access.principal
    if access.principal is None or access.principal.kind != "user":
        raise HTTPException(status_code=401, detail="Authentication required")
    return access.principal


def owner_for_create(access: AccessContext) -> UUID:
    principal = require_user(access)
    if access.mode == DeploymentMode.HOSTED and principal.id == LOCAL_SYSTEM_PRINCIPAL_ID:
        raise HTTPException(status_code=401, detail="Authentication required")
    return principal.id


def authorize_run(
    store: ResearchStore,
    run_id: UUID,
    access: AccessContext,
    *,
    write: bool,
) -> ResearchRunRow:
    row = store.get_run_row(run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Research run not found")
    if access.is_local:
        return row
    require_hosted_auth_config(access)
    if row.is_public_demo:
        if write:
            raise HTTPException(status_code=403, detail="Public demo is read-only")
        return row
    if access.principal is not None and row.owner_principal_id == access.principal.id:
        return row
    raise HTTPException(status_code=404, detail="Research run not found")


def authorize_monitor(store: ResearchStore, monitor_id: UUID, access: AccessContext):
    row = store.get_monitor(monitor_id)
    if row is None:
        raise HTTPException(status_code=404, detail="monitor not found")
    if access.is_local:
        return row
    require_user(access)
    if row.owner_principal_id != access.principal_id:
        raise HTTPException(status_code=404, detail="monitor not found")
    return row


def authorize_template(store: ResearchStore, template_id: UUID, access: AccessContext):
    row = store._session.get(ResearchTemplateRow, template_id)
    if row is None:
        raise HTTPException(status_code=404, detail="template not found")
    if access.is_local:
        return row
    require_user(access)
    if row.owner_principal_id != access.principal_id:
        raise HTTPException(status_code=404, detail="template not found")
    return row


def safe_next_path(raw: str | None, allowlist: str) -> str:
    allowed = {item.strip() or "/" for item in allowlist.split(",") if item.strip()}
    allowed.add("/")
    candidate = (raw or "/").strip()
    if not candidate.startswith("/") or candidate.startswith("//") or "://" in candidate:
        return "/"
    if candidate in allowed or any(
        candidate.startswith(prefix.rstrip("/") + "/") for prefix in allowed if prefix != "/"
    ):
        return candidate
    return "/"
