"""Sanitize published demo content before public exposure."""

from __future__ import annotations

import re

_REDACT_PATTERNS = (
    re.compile(r"/Users/[^\s\"']+"),
    re.compile(r"/home/[^\s\"']+"),
    re.compile(r"localhost:\d+"),
    re.compile(r"127\.0\.0\.1(?::\d+)?"),
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*\S+"),
    re.compile(r"(?i)CREDENTIAL_ENCRYPTION_KEY\s*[:=]\s*\S+"),
    re.compile(r"(?i)Authorization:\s*\S+"),
)


def sanitize_text(text: str | None) -> str:
    if not text:
        return ""
    out = text
    for pattern in _REDACT_PATTERNS:
        out = pattern.sub("[redacted]", out)
    return out
