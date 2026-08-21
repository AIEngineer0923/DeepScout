"""OAuth 2.1 Authorization Code + PKCE via Authlib. No home-grown token exchange."""

from __future__ import annotations

from authlib.integrations.httpx_client import OAuth2Client
from deepscout_core.settings import Settings, get_settings
from deepscout_persistence.identity import (
    consume_oauth_state,
    create_session,
    record_event,
    revoke_all_sessions,
    revoke_session,
    save_oauth_state,
    upsert_oauth_principal,
)
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from deepscout_api.access import SESSION_COOKIE, load_access, require_user, safe_next_path
from deepscout_api.deps import get_research_store

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

GITHUB = {
    "authorize": "https://github.com/login/oauth/authorize",
    "token": "https://github.com/login/oauth/access_token",
    "user": "https://api.github.com/user",
    "emails": "https://api.github.com/user/emails",
    "scope": "read:user user:email",
}
GOOGLE = {
    "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
    "token": "https://oauth2.googleapis.com/token",
    "user": "https://openidconnect.googleapis.com/v1/userinfo",
    "scope": "openid email profile",
}


def _cookie_secure(settings: Settings) -> bool:
    return settings.public_base_url.startswith("https://")


def _set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        secure=_cookie_secure(settings),
        samesite="lax",
        max_age=14 * 24 * 3600,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def _client_id_secret(settings: Settings, provider: str) -> tuple[str, str]:
    if provider == "github":
        if not settings.github_oauth_client_id or not settings.github_oauth_client_secret:
            raise HTTPException(status_code=503, detail="GitHub login is not configured")
        return settings.github_oauth_client_id, settings.github_oauth_client_secret.get_secret_value()
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        raise HTTPException(status_code=503, detail="Google login is not configured")
    return settings.google_oauth_client_id, settings.google_oauth_client_secret.get_secret_value()


@router.get("/me")
def auth_me(
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    access = load_access(request, store._session, settings)
    if access.principal is None:
        return {"authenticated": False, "mode": access.mode.value, "hosted_auth_ready": access.hosted_auth_ready}
    principal = access.principal
    return {
        "authenticated": True,
        "mode": access.mode.value,
        "hosted_auth_ready": access.hosted_auth_ready,
        "id": str(principal.id),
        "kind": principal.kind,
        "display_name": principal.display_name,
        "email": principal.email if principal.email_verified else None,
        "status": principal.status,
    }


@router.get("/login/{provider}")
def login_start(
    provider: str,
    request: Request,
    next: str | None = Query(default="/"),
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
):
    if settings.is_hosted() and not settings.hosted_auth_ready():
        raise HTTPException(status_code=503, detail="Hosted authentication is not configured")
    if provider not in {"github", "google"}:
        raise HTTPException(status_code=404, detail="unknown provider")
    client_id, client_secret = _client_id_secret(settings, provider)
    spec = GITHUB if provider == "github" else GOOGLE
    next_path = safe_next_path(next, settings.oauth_redirect_allowlist)
    state, verifier = save_oauth_state(store._session, provider=provider, next_path=next_path)
    redirect_uri = f"{settings.public_base_url.rstrip('/')}/api/v1/auth/callback/{provider}"
    client = OAuth2Client(
        client_id=client_id,
        client_secret=client_secret,
        code_challenge_method="S256",
        scope=spec["scope"],
        redirect_uri=redirect_uri,
    )
    url, _ = client.create_authorization_url(
        spec["authorize"],
        state=state,
        code_verifier=verifier,
        nonce=state if provider == "google" else None,
    )
    return RedirectResponse(url, status_code=302)


@router.get("/callback/{provider}")
def login_callback(
    provider: str,
    request: Request,
    code: str | None = None,
    state: str | None = None,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
):
    if provider not in {"github", "google"} or not code or not state:
        raise HTTPException(status_code=400, detail="invalid callback")
    saved = consume_oauth_state(store._session, state, provider)
    if saved is None:
        raise HTTPException(status_code=400, detail="invalid oauth state")
    client_id, client_secret = _client_id_secret(settings, provider)
    spec = GITHUB if provider == "github" else GOOGLE
    redirect_uri = f"{settings.public_base_url.rstrip('/')}/api/v1/auth/callback/{provider}"
    client = OAuth2Client(
        client_id=client_id,
        client_secret=client_secret,
        code_challenge_method="S256",
        redirect_uri=redirect_uri,
    )
    client.fetch_token(
        spec["token"],
        code=code,
        code_verifier=saved.code_verifier,
    )
    userinfo = client.get(spec["user"]).json()
    email = None
    email_verified = False
    display_name = ""
    avatar = None
    provider_account_id = ""
    if provider == "github":
        provider_account_id = str(userinfo.get("id") or "")
        display_name = str(userinfo.get("name") or userinfo.get("login") or "GitHub user")
        avatar = userinfo.get("avatar_url")
        email = userinfo.get("email")
        emails = client.get(spec["emails"]).json() if spec.get("emails") else []
        if isinstance(emails, list):
            primary = next((item for item in emails if item.get("primary") and item.get("verified")), None)
            chosen = primary or next((item for item in emails if item.get("verified")), None)
            if chosen:
                email = chosen.get("email")
                email_verified = True
    else:
        provider_account_id = str(userinfo.get("sub") or "")
        display_name = str(userinfo.get("name") or "Google user")
        avatar = userinfo.get("picture")
        email = userinfo.get("email")
        email_verified = bool(userinfo.get("email_verified"))
    if not provider_account_id:
        raise HTTPException(status_code=400, detail="provider identity missing")
    principal = upsert_oauth_principal(
        store._session,
        provider=provider,
        provider_account_id=provider_account_id,
        display_name=display_name,
        email=email,
        email_verified=email_verified,
        avatar_url=avatar,
    )
    token = create_session(store._session, principal.id)
    web = settings.cors_origins.split(",")[0].strip() or "http://localhost:3000"
    response = RedirectResponse(f"{web}{saved.next_path}", status_code=302)
    _set_session_cookie(response, token, settings)
    return response


@router.post("/logout")
def logout(
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        revoke_session(store._session, token)
        record_event(store._session, None, "logout")
    response = JSONResponse({"ok": True})
    _clear_session_cookie(response)
    return response


@router.post("/logout-all")
def logout_all(
    request: Request,
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    access = load_access(request, store._session, settings)
    principal = require_user(access)
    count = revoke_all_sessions(store._session, principal.id)
    record_event(store._session, principal.id, "logout_all")
    response = JSONResponse({"revoked": count})
    _clear_session_cookie(response)
    return response
