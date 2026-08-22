"""Contextual chunk enrichment for embedding — source text stays immutable."""

from __future__ import annotations


def build_context_text(
    *,
    chunk_text: str,
    document_title: str = "",
    section_title: str | None = None,
    source_url: str = "",
) -> str:
    """Prefix document/section context for dense embedding without altering evidence text."""
    parts: list[str] = []
    if document_title.strip():
        parts.append(f"Document: {document_title.strip()[:200]}")
    if section_title and section_title.strip():
        parts.append(f"Section: {section_title.strip()[:200]}")
    if source_url.strip():
        parts.append(f"Source: {source_url.strip()[:300]}")
    parts.append(chunk_text)
    return "\n".join(parts)
