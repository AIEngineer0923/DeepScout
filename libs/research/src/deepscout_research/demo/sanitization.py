"""Sanitize published demo content before public exposure."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_REDACT_PATTERNS = (
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"/home/[^\s\"']+"),
    re.compile(r"localhost:\d+"),
    re.compile(r"127\.0\.0\.1(?::\d+)?"),
    re.compile(r"\bsk-(?:proj-|ant-|live-)?[A-Za-z0-9_\-]{8,}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"\b(?:eyJ[A-Za-z0-9_-]{8,}\.){2}[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(
        r"(?i)(api[_-]?key|secret|token|password|signature|credential)"
        r"\s*[:=]\s*[^\s&;\"']+"
    ),
    re.compile(r"(?i)CREDENTIAL_ENCRYPTION_KEY\s*[:=]\s*\S+"),
    re.compile(r"(?i)Authorization:\s*[^\r\n]+"),
)


def sanitize_text(text: str | None) -> str:
    if not text:
        return ""
    out = text
    for pattern in _REDACT_PATTERNS:
        out = pattern.sub("[redacted]", out)
    return out


def sanitize_url(value: str | None) -> str:
    """Remove credentials, query parameters, and fragments from a public URL."""
    if not value:
        return ""
    cleaned = sanitize_text(value)
    try:
        parsed = urlsplit(cleaned)
    except ValueError:
        return "[redacted]"
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "[redacted]"
    host = parsed.hostname
    if parsed.port:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, "", ""))


def sanitize_public_value(value: Any, *, key: str | None = None) -> Any:
    """Recursively redact strings before a published artifact crosses the public boundary."""
    if isinstance(value, str):
        if key and key.lower() in {"url", "canonical_url", "source_url", "final_url"}:
            return sanitize_url(value)
        return sanitize_text(value)
    if isinstance(value, Mapping):
        return {
            str(item_key): sanitize_public_value(item, key=str(item_key))
            for item_key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return [sanitize_public_value(item) for item in value]
    return value
