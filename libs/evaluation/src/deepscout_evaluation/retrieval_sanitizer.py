"""Sanitization for production-derived regression fixtures — no secrets in Git."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from deepscout_evaluation.regression_origins import RegressionOrigin

_SECRET_PATTERNS = (
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]+=*", re.I),
    re.compile(r"-----BEGIN [A-Z ]+-----"),
    re.compile(r"Cookie:\s*\S+", re.I),
    re.compile(r"Authorization:\s*\S+", re.I),
    re.compile(r"postgresql(\+[^:]+)?://[^\s]+", re.I),
    re.compile(r"mongodb(\+srv)?://[^\s]+", re.I),
)
_EMAIL = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
_UUID = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\b",
    re.I,
)
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
_SENSITIVE_QUERY_KEYS = frozenset(
    {"token", "access_token", "api_key", "apikey", "key", "signature", "sig", "secret"}
)
_FILESYSTEM_PATH = re.compile(r"(?:^|[\s\"'])(/[\w./-]+)")
_TENANT_KEYS = frozenset(
    {
        "owner_principal_id",
        "tenant_id",
        "user_id",
        "session_id",
        "api_key",
        "principal_id",
        "cookie",
        "authorization",
    }
)


def contains_secret_material(text: str) -> bool:
    return any(pattern.search(text) for pattern in _SECRET_PATTERNS)


def contains_private_url(url: str) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if any(marker in host for marker in _PRIVATE_HOSTS):
        return True
    if parsed.query:
        params = parse_qs(parsed.query)
        if any(key.lower() in _SENSITIVE_QUERY_KEYS for key in params):
            return True
    return False


def sanitize_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not host:
        return "https://example.invalid/unknown"
    if contains_private_url(url):
        return f"https://example.invalid/{host.replace('.', '-')}"
    if parsed.query and any(k.lower() in _SENSITIVE_QUERY_KEYS for k in parse_qs(parsed.query)):
        return "https://example.invalid/redacted-query"
    return url.split("?")[0] if "?" in url else url


def sanitize_text(text: str) -> str:
    cleaned = _EMAIL.sub("[redacted-email]", text)
    cleaned = _UUID.sub("[redacted-uuid]", cleaned)
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub("[redacted-secret]", cleaned)
    cleaned = _FILESYSTEM_PATH.sub(" [redacted-path]", cleaned)
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
    for key in _TENANT_KEYS:
        out.pop(key, None)
    if out.get("origin") == RegressionOrigin.PRODUCTION_UNSANITIZED:
        raise ValueError("production_unsanitized origin cannot be exported")
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
        if origin == RegressionOrigin.PRODUCTION_UNSANITIZED:
            violations.append(f"{case.get('case_id')}: origin production_unsanitized")
        if origin == RegressionOrigin.PRODUCTION_CANDIDATE:
            violations.append(f"{case.get('case_id')}: production_candidate must not be committed")
    return violations
