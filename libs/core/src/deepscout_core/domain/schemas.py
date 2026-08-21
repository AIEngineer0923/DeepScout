"""Pydantic domain/API schemas (LangChain-independent)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from deepscout_core.domain.budget import ResearchBudget
from deepscout_core.domain.enums import (
    ContradictionEvidenceStatus,
    ResearchQuestionStatus,
    ResearchRunStatus,
    ResearchTaskStatus,
    SourceType,
    ToolExecutionStatus,
)
from deepscout_core.domain.usage import RunUsageSummary


class ResearchRunCreate(BaseModel):
    goal: str = Field(min_length=1, max_length=8000)
    budget: ResearchBudget | None = None
    research_mode: Literal["quick", "standard", "deep"] | None = None
    output_language: str = Field(default="en", min_length=2, max_length=16)


class ResearchRunRead(BaseModel):
    id: UUID
    goal: str
    status: ResearchRunStatus
    llm_provider: str
    llm_model: str
    budget: ResearchBudget
    usage: RunUsageSummary | None = None
    termination_reason: str | None = None
    research_mode: Literal["quick", "standard", "deep"] | None = None
    output_language: str = "en"
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class PlannerTask(BaseModel):
    task_key: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_-]+$")
    objective: str = Field(min_length=1, max_length=2000)
    question_text: str | None = Field(default=None, max_length=2000)
    depends_on: list[str] = Field(default_factory=list, max_length=20)
    priority: int = Field(default=3, ge=1, le=5)
    allowed_tools: list[str] = Field(default_factory=lambda: ["web_search"], max_length=10)


class ResearchPlanWrite(BaseModel):
    strategy: str = Field(min_length=1, max_length=16000)
    success_criteria: str = Field(min_length=1, max_length=8000)
    questions: list[str] = Field(default_factory=list, max_length=50)
    tasks: list[PlannerTask] = Field(default_factory=list, max_length=50)


class PlannerQuestion(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    priority: int = Field(default=3, ge=1, le=5)


class PlannerOutput(BaseModel):
    """Structured planner output — no free-text parsing."""

    approach: str = Field(min_length=1, max_length=4000)
    success_criteria: str = Field(min_length=1, max_length=4000)
    questions: list[PlannerQuestion] = Field(min_length=1, max_length=20)


class SearchResult(BaseModel):
    """Normalized web search candidate — not a Source or SourceSnapshot."""

    url: str = Field(min_length=1, max_length=2048)
    title: str = Field(default="", max_length=512)
    snippet: str = Field(default="", max_length=8000)
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class SearchCandidateWrite(BaseModel):
    query: str = Field(min_length=1, max_length=512)
    provider: str = Field(min_length=1, max_length=32)
    results: list[SearchResult] = Field(default_factory=list, max_length=50)
    question_id: UUID | None = None


class ResearchQuestionRead(BaseModel):
    id: UUID
    text: str
    status: ResearchQuestionStatus
    sort_order: int


class ResearchTaskRead(BaseModel):
    id: UUID
    task_key: str
    objective: str
    status: ResearchTaskStatus
    priority: int
    depends_on: list[str]
    allowed_tools: list[str]
    question_id: UUID | None = None
    worker_id: UUID | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    retry_count: int = 0


class SourceWrite(BaseModel):
    canonical_url: str = Field(min_length=1, max_length=2048)
    title: str = Field(default="", max_length=512)
    domain: str = Field(default="", max_length=255)
    source_type: SourceType = SourceType.WEB


class SourceSnapshotWrite(BaseModel):
    content: str = Field(min_length=1, max_length=500_000)
    mime_type: str = Field(default="text/html", max_length=128)
    retrieval_metadata: dict[str, str] = Field(default_factory=dict)


class ClaimWrite(BaseModel):
    statement: str = Field(min_length=1, max_length=8000)
    source_id: UUID | None = None
    question_id: UUID | None = None


class EvidenceWrite(BaseModel):
    snapshot_id: UUID
    quote: str = Field(min_length=1, max_length=16000)
    locator: str = Field(default="", max_length=512)
    support_strength: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ContradictionWrite(BaseModel):
    claim_a_id: UUID
    claim_b_id: UUID
    description: str = Field(min_length=1, max_length=8000)
    evidence_status: ContradictionEvidenceStatus = ContradictionEvidenceStatus.SUFFICIENT


class ToolExecutionWrite(BaseModel):
    tool_name: str = Field(min_length=1, max_length=128)
    input_summary: str = Field(default="", max_length=4000)
    output_summary: str = Field(default="", max_length=4000)
    status: ToolExecutionStatus = ToolExecutionStatus.SUCCESS
    duration_ms: int = Field(default=0, ge=0)


class DecisionWrite(BaseModel):
    recommendation: str = Field(min_length=1, max_length=16000)
    rationale: str = Field(min_length=1, max_length=16000)
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_claim_ids: list[UUID] = Field(min_length=1)


class CriticResult(BaseModel):
    passed: bool
    artifact_type: str = Field(min_length=1, max_length=64)
    severity: str = Field(default="pass", max_length=32)
    issues: list[str] = Field(default_factory=list, max_length=20)


class SynthesisOutput(BaseModel):
    recommendation: str = Field(min_length=1, max_length=16000)
    rationale: str = Field(min_length=1, max_length=16000)
    uncertainty_state: str = Field(min_length=1, max_length=64)
    supporting_claim_ids: list[UUID] = Field(default_factory=list, max_length=50)


class ReportWrite(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    body_markdown: str = Field(min_length=1, max_length=200_000)
    cited_evidence_ids: list[UUID] = Field(min_length=1)
