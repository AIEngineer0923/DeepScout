"""Deterministic text helpers for extraction and verification."""

from __future__ import annotations

import re


def normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def normalize_match_key(text: str) -> str:
    cleaned = normalize_whitespace(text).lower()
    return re.sub(r"[^\w\s]", "", cleaned)


def locate_quote_in_content(snippet: str, content: str, *, min_len: int = 24) -> str | None:
    """Return an exact quote span from content when snippet text is present."""
    snippet = snippet.strip()
    if len(snippet) < min_len:
        return None
    if snippet in content:
        return snippet
    key = normalize_match_key(snippet)
    if len(key) < min_len:
        return None
    normalized_content = normalize_match_key(content)
    start = normalized_content.find(key)
    if start < 0:
        return None
    # Map back approximately by scanning original content words.
    words = normalize_whitespace(content).split()
    snippet_words = normalize_whitespace(snippet).split()
    if not snippet_words:
        return None
    first = snippet_words[0].lower()
    for index in range(len(words)):
        if words[index].lower().startswith(first[: max(3, len(first))]):
            candidate = " ".join(words[index : index + len(snippet_words)])
            if normalize_match_key(candidate) == key:
                return candidate
    return None
