"""Deterministic retrieval planner — strategy only, not factual truth."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from deepscout_core.domain.enums import AgentRole
from deepscout_core.settings import Settings
from pydantic import BaseModel, Field, field_validator


class RetrievalRoute(StrEnum):
    LEXICAL = "lexical"
    DENSE = "dense"
    HYBRID = "hybrid"
    RELATIONAL = "relational"
    WEB = "web"


class QueryPlan(BaseModel):
    """Structured retrieval plan — no free-form natural language strategy."""

    original_query: str
    lexical_query: str
    semantic_query: str
    run_id: UUID
    task_id: UUID | None = None
    entities: list[str] = Field(default_factory=list, max_length=20)
    source_ids: list[UUID] = Field(default_factory=list, max_length=50)
    fresher_than: datetime | None = None
    mode: Literal["dense", "lexical", "hybrid"] = "hybrid"
    corpus: Literal["raw", "compiled", "both"] = "raw"
    routes: list[RetrievalRoute] = Field(default_factory=list, max_length=6)
    top_k: int = Field(default=8, ge=1, le=32)
    candidate_k: int = Field(default=20, ge=1, le=64)
    counter_evidence: bool = False
    skip_retrieval: bool = False
    skip_reason: str = ""

    @field_validator("original_query", "lexical_query", "semantic_query")
    @classmethod
    def normalize_whitespace(cls, value: str) -> str:
        return " ".join(value.split())


_ENTITY_PATTERNS = (
    re.compile(r"\bCVE-\d{4}-\d+\b", re.I),
    re.compile(r"\bv?\d+\.\d+(?:\.\d+)?\b"),
    re.compile(r"\b[A-Z]{2,}(?:-[A-Z0-9]+)+\b"),
)

_COMPILED_HINTS = (
    "have we learned",
    "what do we know",
    "summarize our",
    "accumulated understanding",
    "wiki",
)
_RAW_HINTS = (
    "what does source",
    "find evidence",
    "quote",
    "exact passage",
    "snapshot",
)
_BOTH_HINTS = (
    "contradict",
    "contradiction",
    "conflict",
)


def _extract_entities(query: str) -> list[str]:
    found: list[str] = []
    for pattern in _ENTITY_PATTERNS:
        for match in pattern.findall(query):
            token = match.strip()
            if token and token not in found:
                found.append(token[:120])
    return found[:20]


def _infer_corpus(query: str) -> Literal["raw", "compiled", "both"]:
    lowered = query.lower()
    if any(hint in lowered for hint in _BOTH_HINTS):
        return "both"
    if any(hint in lowered for hint in _COMPILED_HINTS):
        return "compiled"
    if any(hint in lowered for hint in _RAW_HINTS):
        return "raw"
    return "raw"


def plan_retrieval_query(
    *,
    query: str,
    run_id: UUID,
    settings: Settings,
    task_id: UUID | None = None,
    source_ids: list[UUID] | None = None,
    role: AgentRole = AgentRole.EXTRACTOR,
    document_token_estimate: int | None = None,
    counter_evidence: bool = False,
    fresher_than: datetime | None = None,
) -> QueryPlan:
    cleaned = " ".join(query.split())
    entities = _extract_entities(cleaned)
    corpus = _infer_corpus(cleaned)
    mode = (
        settings.retrieval_mode
        if settings.retrieval_mode in {"dense", "lexical", "hybrid"}
        else "hybrid"
    )
    top_k = _role_top_k(role, settings.retrieval_top_k)
    candidate_k = max(settings.retrieval_candidate_k, top_k)

    if document_token_estimate is not None and document_token_estimate <= 1000:
        return QueryPlan(
            original_query=cleaned,
            lexical_query=cleaned,
            semantic_query=cleaned,
            run_id=run_id,
            task_id=task_id,
            entities=entities,
            source_ids=list(source_ids or []),
            mode=mode,
            corpus=corpus,
            routes=[RetrievalRoute.RELATIONAL],
            top_k=top_k,
            candidate_k=candidate_k,
            counter_evidence=counter_evidence,
            skip_retrieval=True,
            skip_reason="long_context_not_needed",
        )

    routes = [RetrievalRoute.HYBRID if mode == "hybrid" else RetrievalRoute(mode)]
    if entities:
        routes.append(RetrievalRoute.LEXICAL)

    return QueryPlan(
        original_query=cleaned,
        lexical_query=cleaned,
        semantic_query=cleaned,
        run_id=run_id,
        task_id=task_id,
        entities=entities,
        source_ids=list(source_ids or []),
        fresher_than=fresher_than,
        mode=mode,
        corpus=corpus,
        routes=routes,
        top_k=top_k,
        candidate_k=candidate_k,
        counter_evidence=counter_evidence,
    )


def _role_top_k(role: AgentRole, default: int) -> int:
    match role:
        case AgentRole.RESEARCH_WORKER:
            return min(default + 4, 16)
        case AgentRole.EXTRACTOR:
            return default
        case AgentRole.VERIFIER | AgentRole.CONTRADICTION:
            return min(default + 2, 12)
        case AgentRole.CRITIC:
            return min(default + 2, 12)
        case _:
            return default
