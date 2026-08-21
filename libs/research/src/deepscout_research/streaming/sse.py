"""SSE framing for durable research-run event delivery."""

from __future__ import annotations

import json
from typing import Any


def parse_last_event_id(header_value: str | None, query_after: int | None) -> int:
    """Prefer explicit ?after=; otherwise Last-Event-ID. Invalid values → 0."""
    if query_after is not None:
        return max(0, int(query_after))
    if header_value and str(header_value).strip().isdigit():
        return max(0, int(str(header_value).strip()))
    return 0


def format_sse_event(*, sequence: int, event_type: str, payload: dict[str, Any]) -> str:
    # Keep unnamed `message` events so EventSource.onmessage fires.
    # Event type travels in JSON `type` (and payload already includes layer).
    del event_type
    body = json.dumps(payload, default=str, separators=(",", ":"))
    return f"id: {sequence}\ndata: {body}\n\n"


def format_sse_comment(text: str = "keepalive") -> str:
    return f": {text}\n\n"
