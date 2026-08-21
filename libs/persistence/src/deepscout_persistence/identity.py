"""Principal, session, and credential persistence helpers."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from deepscout_core.deployment import LOCAL_SYSTEM_PRINCIPAL_ID
from sqlalchemy import select
from sqlalchemy.orm import Session

from deepscout_persistence.models import (
    AuthAccountRow,
    AuthEventRow,
    OAuthStateRow,
    PrincipalRow,
    ProviderCredentialRow,
    SessionRow,
)

SESSION_TTL = timedelta(days=14)
OAUTH_STATE_TTL = timedelta(minutes=10)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_principal(session: Session, principal_id: UUID) -> PrincipalRow | None:
    return session.get(PrincipalRow, principal_id)


def get_local_system(session: Session) -> PrincipalRow:
    row = session.get(PrincipalRow, LOCAL_SYSTEM_PRINCIPAL_ID)
    if row is None:
        row = PrincipalRow(
            id=LOCAL_SYSTEM_PRINCIPAL_ID,
            kind="local_system",
            display_name="Local operator",
            status="active",
        )
        session.add(row)
        session.flush()
    return row


def record_event(
    session: Session, principal_id: UUID | None, event_type: str, detail: str = ""
) -> None:
    session.add(
        AuthEventRow(
            id=uuid4(), principal_id=principal_id, event_type=event_type, detail=detail[:256]
        )
    )


def create_session(session: Session, principal_id: UUID) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    session.add(
        SessionRow(
            id=uuid4(),
            principal_id=principal_id,
            token_hash=hash_token(token),
            expires_at=now + SESSION_TTL,
            created_at=now,
            last_seen_at=now,
        )
    )
    session.flush()
    return token


def resolve_session(session: Session, token: str) -> PrincipalRow | None:
    if not token:
        return None
    row = session.scalar(select(SessionRow).where(SessionRow.token_hash == hash_token(token)))
    if row is None or row.revoked_at is not None:
        return None
    now = datetime.now(UTC)
    if row.expires_at <= now:
        return None
    principal = session.get(PrincipalRow, row.principal_id)
    if principal is None or principal.status != "active":
        return None
    row.last_seen_at = now
    return principal


def revoke_session(session: Session, token: str) -> None:
    row = session.scalar(select(SessionRow).where(SessionRow.token_hash == hash_token(token)))
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)


def revoke_all_sessions(session: Session, principal_id: UUID) -> int:
    now = datetime.now(UTC)
    rows = session.scalars(
        select(SessionRow).where(
            SessionRow.principal_id == principal_id, SessionRow.revoked_at.is_(None)
        )
    ).all()
    for row in rows:
        row.revoked_at = now
    return len(rows)


def upsert_oauth_principal(
    session: Session,
    *,
    provider: str,
    provider_account_id: str,
    display_name: str,
    email: str | None,
    email_verified: bool,
    avatar_url: str | None,
) -> PrincipalRow:
    account = session.scalar(
        select(AuthAccountRow).where(
            AuthAccountRow.provider == provider,
            AuthAccountRow.provider_account_id == provider_account_id,
        )
    )
    if account is not None:
        principal = session.get(PrincipalRow, account.principal_id)
        assert principal is not None
        principal.last_login_at = datetime.now(UTC)
        if display_name:
            principal.display_name = display_name[:128]
        if avatar_url:
            principal.avatar_url = avatar_url[:2048]
        if email and email_verified and not principal.email:
            principal.email = email[:320]
            principal.email_verified = True
        record_event(session, principal.id, "login", provider)
        return principal

    if email and email_verified:
        existing = session.scalar(
            select(PrincipalRow).where(
                PrincipalRow.email == email, PrincipalRow.email_verified.is_(True)
            )
        )
        if existing is not None:
            session.add(
                AuthAccountRow(
                    id=uuid4(),
                    principal_id=existing.id,
                    provider=provider,
                    provider_account_id=provider_account_id,
                )
            )
            existing.last_login_at = datetime.now(UTC)
            record_event(session, existing.id, "account_link", provider)
            return existing

    principal = PrincipalRow(
        id=uuid4(),
        kind="user",
        display_name=(display_name or provider)[:128],
        email=email[:320] if email and email_verified else None,
        email_verified=bool(email and email_verified),
        avatar_url=avatar_url[:2048] if avatar_url else None,
        status="active",
        last_login_at=datetime.now(UTC),
    )
    session.add(principal)
    session.flush()
    session.add(
        AuthAccountRow(
            id=uuid4(),
            principal_id=principal.id,
            provider=provider,
            provider_account_id=provider_account_id,
        )
    )
    record_event(session, principal.id, "login", provider)
    return principal


def save_oauth_state(session: Session, *, provider: str, next_path: str) -> tuple[str, str]:
    state = secrets.token_urlsafe(24)
    verifier = secrets.token_urlsafe(48)
    session.add(
        OAuthStateRow(
            id=uuid4(),
            state=state,
            code_verifier=verifier,
            provider=provider,
            next_path=next_path,
            expires_at=datetime.now(UTC) + OAUTH_STATE_TTL,
        )
    )
    session.flush()
    return state, verifier


def consume_oauth_state(session: Session, state: str, provider: str) -> OAuthStateRow | None:
    row = session.scalar(select(OAuthStateRow).where(OAuthStateRow.state == state))
    if row is None or row.provider != provider or row.expires_at <= datetime.now(UTC):
        return None
    session.delete(row)
    session.flush()
    return row


def get_credential(
    session: Session, principal_id: UUID, provider: str
) -> ProviderCredentialRow | None:
    return session.scalar(
        select(ProviderCredentialRow).where(
            ProviderCredentialRow.principal_id == principal_id,
            ProviderCredentialRow.provider == provider,
        )
    )


def list_credentials(session: Session, principal_id: UUID) -> list[ProviderCredentialRow]:
    return list(
        session.scalars(
            select(ProviderCredentialRow).where(ProviderCredentialRow.principal_id == principal_id)
        ).all()
    )


def delete_credential(session: Session, principal_id: UUID, provider: str) -> bool:
    row = get_credential(session, principal_id, provider)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def delete_principal_data(session: Session, principal_id: UUID) -> None:
    from deepscout_persistence.models import ResearchMonitorRow, ResearchRunRow, ResearchTemplateRow

    for monitor in session.scalars(
        select(ResearchMonitorRow).where(ResearchMonitorRow.owner_principal_id == principal_id)
    ):
        session.delete(monitor)
    session.flush()
    for template in session.scalars(
        select(ResearchTemplateRow).where(ResearchTemplateRow.owner_principal_id == principal_id)
    ):
        session.delete(template)
    session.flush()
    for run in session.scalars(
        select(ResearchRunRow).where(ResearchRunRow.owner_principal_id == principal_id)
    ):
        session.delete(run)
    session.flush()
    principal = session.get(PrincipalRow, principal_id)
    if principal is not None:
        session.delete(principal)
    session.flush()
