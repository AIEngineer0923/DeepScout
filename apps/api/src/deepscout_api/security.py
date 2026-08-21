"""HTTP security headers, CORS policy, and in-process rate limiting."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from deepscout_core.settings import Settings
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, Response

MUTATING_PREFIXES = (
    "/api/v1/research-runs",
    "/api/v1/research-monitors",
    "/api/v1/research-templates",
    "/api/v1/account",
    "/api/v1/auth/logout",
    "/api/v1/smoke/",
)
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _request_is_https(request: Request) -> bool:
    if request.url.scheme == "https":
        return True
    proto = request.headers.get("x-forwarded-proto", "")
    return proto.split(",")[0].strip().lower() == "https"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'",
        )
        response.headers.setdefault("Cache-Control", "no-store")
        if _request_is_https(request):
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains",
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, settings: Settings, max_keys: int = 4096):
        super().__init__(app)
        self._settings = settings
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._max_keys = max_keys

    def _allow(self, key: str, limit: int, window_s: int) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window_s:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            if len(self._hits) > self._max_keys:
                stale = [
                    existing
                    for existing, values in self._hits.items()
                    if existing != key and (not values or now - values[-1] > window_s)
                ]
                for existing in stale:
                    self._hits.pop(existing, None)
            return True

    async def dispatch(self, request: Request, call_next) -> Response:
        from deepscout_core.settings import get_settings

        live = get_settings()
        if self._settings.rate_limit_enabled:
            settings = self._settings
        elif live.rate_limit_enabled or live.is_hosted():
            settings = live
        else:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        general_ok = self._allow(
            f"all:{client}",
            settings.rate_limit_max_requests,
            settings.rate_limit_window_s,
        )
        if not general_ok:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        mutating = request.method in MUTATING_METHODS and any(
            request.url.path.startswith(prefix) for prefix in MUTATING_PREFIXES
        )
        if mutating and not self._allow(
            f"mutate:{client}",
            settings.rate_limit_mutating_max,
            settings.rate_limit_window_s,
        ):
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        return await call_next(request)


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Reject cross-site mutating requests whose Origin is not in CORS_ORIGINS.

    Missing Origin is allowed (non-browser clients and TestClient). A present
    mismatched Origin is CSRF, not CORS.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in MUTATING_METHODS:
            return await call_next(request)
        origin = request.headers.get("origin")
        if not origin:
            return await call_next(request)
        from deepscout_core.settings import get_settings

        allowed = {item.rstrip("/") for item in cors_origins(get_settings())}
        if origin.rstrip("/") not in allowed:
            return JSONResponse({"detail": "Invalid origin"}, status_code=403)
        return await call_next(request)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, max_bytes: int):
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.method not in {"POST", "PUT", "PATCH"}:
            return await call_next(request)
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > self._max_bytes:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        body = await request.body()
        if len(body) > self._max_bytes:
            return JSONResponse({"detail": "Request body too large"}, status_code=413)
        return await call_next(request)


def cors_origins(settings: Settings) -> list[str]:
    configured = [item.strip() for item in settings.cors_origins.split(",") if item.strip()]
    return configured or ["http://localhost:3000", "http://127.0.0.1:3000"]


def install_security_middleware(app: FastAPI, settings: Settings) -> None:
    origins = cors_origins(settings)
    if "*" in origins:
        raise RuntimeError("Wildcard CORS origins are not allowed")
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(OriginCheckMiddleware)
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Last-Event-ID"],
    )
