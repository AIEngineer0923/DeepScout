"""Sanitization for production-derived regression fixtures — no secrets in Git."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

_SECRET_PATTERNS = (
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.I),
    re.compile(r"-----BEGIN [A-Z ]+-----"),
)
_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_PRIVATE_HOSTS = (
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    ".internal",
    ".local",
    "supabase.co",
    "railway.app",
    "vercel.app",
)


def contains_secret_material(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def sanitize_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return "https://example.invalid/unknown"
    if any(marker in host for marker in _PRIVATE_HOSTS):
        return f"https://example.invalid/{host.replace('.', '-')}"
    if host.count(".") >= 2:
        return f"https://example.invalid/{parsed.path.lstrip('/') or 'source'}"
    return url


def sanitize_text(text: str) -> str:
    cleaned = _EMAIL.sub("[redacted-email]", text)
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub("[redacted-secret]", cleaned)
    return cleaned


def sanitize_regression_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Return a sanitized copy suitable for repository commit."""
    blob = str(candidate)
    if contains_secret_material(blob):
        raise ValueError("candidate contains secret-like material; refuse to export")
    out = dict(candidate)
    out["query"] = sanitize_text(str(out.get("query", "")))
    out["sanitized_notes"] = sanitize_text(str(out.get("sanitized_notes", "")))
    if "original_failure_summary" in out:
        out["original_failure_summary"] = sanitize_text(str(out["original_failure_summary"]))
    domains = out.get("relevant_source_domains")
    if isinstance(domains, list):
        out["relevant_source_domains"] = [
            urlparse(sanitize_url(f"https://{d}" if "://" not in d else d)).hostname or d
            for d in domains
        ]
    for key in ("owner_principal_id", "tenant_id", "user_id", "session_id", "api_key"):
        out.pop(key, None)
    return out


def validate_fixture_privacy(fixture: dict[str, Any]) -> list[str]:
    """Return privacy violations found in a fixture (empty if safe)."""
    violations: list[str] = []
    blob = str(fixture)
    if contains_secret_material(blob):
        violations.append("secret-like pattern detected")
    if _EMAIL.search(blob):
        violations.append("email address detected")
    for case in fixture.get("cases", []):
        origin = case.get("origin", "")
        if origin == "production_unsanitized":
            violations.append(f"{case.get('case_id')}: origin production_unsanitized")
    return violations
