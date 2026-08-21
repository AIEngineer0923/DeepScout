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
    "/api/v1/smoke/",
)
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


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
        if request.url.scheme == "https":
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=63072000; includeSubDomains",
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, settings: Settings):
        super().__init__(app)
        self._settings = settings
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _allow(self, key: str, limit: int, window_s: int) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            while bucket and now - bucket[0] > window_s:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self._settings.rate_limit_enabled:
            return await call_next(request)
        client = request.client.host if request.client else "unknown"
        general_ok = self._allow(
            f"all:{client}",
            self._settings.rate_limit_max_requests,
            self._settings.rate_limit_window_s,
        )
        if not general_ok:
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        mutating = request.method in MUTATING_METHODS and any(
            request.url.path.startswith(prefix) for prefix in MUTATING_PREFIXES
        )
        if mutating and not self._allow(
            f"mutate:{client}",
            self._settings.rate_limit_mutating_max,
            self._settings.rate_limit_window_s,
        ):
            return JSONResponse({"detail": "Rate limit exceeded"}, status_code=429)
        return await call_next(request)


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, max_bytes: int):
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > self._max_bytes:
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
    app.add_middleware(RateLimitMiddleware, settings=settings)
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )
