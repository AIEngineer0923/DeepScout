"""Typed retrieval request/response — chunks are candidates, not evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class RetrievalQuery(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    run_id: UUID
    task_id: UUID | None = None
    top_k: int = Field(default=8, ge=1, le=32)
    candidate_k: int = Field(default=20, ge=1, le=64)
    mode: Literal["dense", "lexical", "hybrid"] = "hybrid"
    apply_rerank: bool = True
    source_ids: list[UUID] = Field(default_factory=list, max_length=50)
    fresher_than: datetime | None = None

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("query must not be empty")
        return cleaned


class RetrievedChunk(BaseModel):
    chunk_id: UUID
    snapshot_id: UUID
    source_id: UUID
    run_id: UUID
    text: str
    locator: str
    ordinal: int
    start_offset: int
    end_offset: int
    dense_score: float | None = None
    lexical_score: float | None = None
    fused_score: float = 0.0
    rerank_score: float | None = None
    dense_rank: int | None = None
    lexical_rank: int | None = None
    retrieval_reason: str = ""
    retrieved_at: datetime | None = None
    section_title: str | None = None
