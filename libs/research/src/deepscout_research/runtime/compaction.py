"""Deterministic context compaction — never treats summaries as evidence."""

from __future__ import annotations

import re

_REF = re.compile(r"\b(?:snapshot|claim|evidence|source):[0-9a-f-]{8,}\b", re.I)


def compact_retrieved(
    items: list[str],
    *,
    char_limit: int,
    keep_head: int = 400,
) -> tuple[list[str], list[str], int]:
    """Drop redundant blobs; keep artifact ids and a truncated head of each item."""
    refs: list[str] = []
    seen: set[str] = set()
    out: list[str] = []
    dropped = 0
    used = 0
    for raw in items:
        text = raw.strip()
        if not text:
            continue
        fingerprint = text[:240]
        if fingerprint in seen:
            dropped += 1
            refs.extend(_REF.findall(text))
            continue
        seen.add(fingerprint)
        refs.extend(_REF.findall(text))
        piece = text if len(text) <= keep_head else text[:keep_head] + "…"
        if used + len(piece) > char_limit:
            dropped += 1
            continue
        out.append(piece)
        used += len(piece)
    # Deduplicate refs while preserving order
    unique_refs = list(dict.fromkeys(refs))
    return out, unique_refs, dropped


def constraint_survives(compacted: str, constraint: str) -> bool:
    return constraint.casefold() in compacted.casefold()
