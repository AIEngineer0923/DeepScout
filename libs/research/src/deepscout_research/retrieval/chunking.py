"""Heading/paragraph-aware chunking with stable snapshot offsets."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from deepscout_research.retrieval.spec import CHUNKING_VERSION, MAX_CHUNKS_PER_SNAPSHOT


@dataclass(frozen=True, slots=True)
class ChunkDraft:
    ordinal: int
    text: str
    start_offset: int
    end_offset: int
    token_count: int
    section_title: str | None
    content_hash: str


def estimate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4)


def chunk_content_hash(*, snapshot_id: str, ordinal: int, text: str, chunking_version: str) -> str:
    payload = f"{snapshot_id}|{ordinal}|{chunking_version}|{text}".encode()
    return hashlib.sha256(payload).hexdigest()


def chunk_snapshot_text(
    text: str,
    *,
    snapshot_id: str,
    target_chars: int = 1800,
    overlap_chars: int = 280,
    max_chunks: int = MAX_CHUNKS_PER_SNAPSHOT,
    chunking_version: str = CHUNKING_VERSION,
) -> list[ChunkDraft]:
    stripped = text.strip()
    if not stripped:
        return []
    windows: list[tuple[int, int, str]] = []
    start = 0
    length = len(text)
    while start < length and len(windows) < max_chunks:
        end = min(length, start + target_chars)
        if end < length:
            boundary = _prefer_boundary(text, start, end)
            end = max(start + 1, boundary)
        piece = text[start:end].strip()
        if piece:
            # Recompute offsets on the original string for the stripped piece.
            piece_start = text.find(piece, start)
            piece_end = piece_start + len(piece)
            windows.append((piece_start, piece_end, piece))
        if end >= length:
            break
        start = max(start + 1, end - overlap_chars)
    drafts: list[ChunkDraft] = []
    current_title: str | None = None
    for ordinal, (start_offset, end_offset, piece) in enumerate(windows):
        heading = _heading(piece)
        if heading:
            current_title = heading
        drafts.append(
            ChunkDraft(
                ordinal=ordinal,
                text=piece,
                start_offset=start_offset,
                end_offset=end_offset,
                token_count=estimate_tokens(piece),
                section_title=current_title,
                content_hash=chunk_content_hash(
                    snapshot_id=snapshot_id,
                    ordinal=ordinal,
                    text=piece,
                    chunking_version=chunking_version,
                ),
            )
        )
    return drafts


def _prefer_boundary(text: str, start: int, end: int) -> int:
    window = text[start:end]
    for needle in ("\n## ", "\n# ", "\n\n", ". ", "? ", "! "):
        idx = window.rfind(needle)
        if idx >= len(window) // 3:
            return start + idx + len(needle.rstrip())
    return end


def _heading(text: str) -> str | None:
    first = text.splitlines()[0].strip() if text else ""
    if first.startswith("#"):
        return first.lstrip("#").strip()[:200] or None
    return None
