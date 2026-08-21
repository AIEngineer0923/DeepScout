"""Deterministic HTML/plain response to readable text for snapshots."""

from __future__ import annotations

import re
from html.parser import HTMLParser


class _MainContentExtractor(HTMLParser):
    """Extract readable text preferring main/article content regions."""

    _SKIP_TAGS = frozenset(
        {
            "script",
            "style",
            "noscript",
            "nav",
            "header",
            "footer",
            "svg",
            "iframe",
            "object",
            "embed",
            "form",
        }
    )
    _BLOCK_TAGS = frozenset({"p", "div", "li", "h1", "h2", "h3", "h4", "br", "section", "td"})
    _TARGET_CLASSES = frozenset(
        {"mw-parser-output", "entry-content", "post-content", "article-body", "article-content"}
    )

    def __init__(self) -> None:
        super().__init__()
        self._skip = False
        self._capture = False
        self._capture_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip = True
            return
        attrs_d = {key: value or "" for key, value in attrs}
        classes = set(attrs_d.get("class", "").split())
        if not self._capture:
            if tag in {"main", "article"} or classes & self._TARGET_CLASSES:
                self._capture = True
                self._capture_depth = 1
        elif self._capture:
            self._capture_depth += 1
        if tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip = False
        if self._capture:
            self._capture_depth -= 1
            if self._capture_depth <= 0:
                self._capture = False

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if not self._capture and not self.parts:
            # Fallback: capture body text when no main region is tagged.
            self._capture = True
            self._capture_depth = 1
        if not self._capture:
            return
        text = data.strip()
        if text:
            self.parts.append(text + " ")


def html_to_text(html: str) -> str:
    parser = _MainContentExtractor()
    parser.feed(html)
    return normalize_plain_text("".join(parser.parts))


def normalize_plain_text(text: str) -> str:
    cleaned = text.replace("\x00", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def sanitize_snapshot_text(text: str) -> str:
    """Remove PostgreSQL-incompatible bytes and obvious binary payloads."""
    cleaned = normalize_plain_text(text)
    if cleaned.startswith("%PDF-"):
        return ""
    return cleaned


def response_to_snapshot_text(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    if "charset=" in content_type.lower():
        _, _, charset_part = content_type.lower().partition("charset=")
        charset = charset_part.split(";")[0].strip() or charset
    raw = body.decode(charset, errors="replace")
    if raw.startswith("%PDF-") or body.lstrip().startswith(b"%PDF-"):
        return ""
    lowered = content_type.lower()
    if (
        "html" in lowered
        or raw.lstrip().startswith("<!DOCTYPE")
        or raw.lstrip().startswith("<html")
    ):
        return sanitize_snapshot_text(html_to_text(raw))
    if "pdf" in lowered:
        return ""
    return sanitize_snapshot_text(normalize_plain_text(raw))


def split_sentences(text: str, *, min_len: int = 40) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if len(part.strip()) >= min_len]
