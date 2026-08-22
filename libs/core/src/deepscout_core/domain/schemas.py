"""Pydantic domain/API schemas (LangChain-independent)."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from deepscout_core.domain.budget import ResearchBudget
from deepscout_core.domain.enums import (
    ContradictionEvidenceStatus,
    PlanDecomposition,
    ResearchQuestionStatus,
    ResearchRunStatus,
    ResearchTaskStatus,
    SourceType,
    ToolExecutionStatus,
)
from deepscout_core.domain.research_preferences import ResearchPreferences
from deepscout_core.domain.usage import RunUsageSummary

WORKER_TOOL_ALLOWLIST = frozenset({"web_search"})


class ResearchRunCreate(BaseModel):
    goal: str = Field(min_length=1, max_length=8000)
    budget: ResearchBudget | None = None
    research_mode: Literal["quick", "standard", "deep"] | None = None
    output_language: str = Field(default="en", min_length=2, max_length=16)
    preferences: ResearchPreferences | None = None


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
    completion_criteria: str = Field(default="", max_length=2000)
    parallel_safe: bool = True
    expected_output: Literal["sources", "facts", "synthesis"] = "facts"
    skill_hint: str | None = Field(default=None, max_length=64)
    dependency_reason: str = Field(default="", max_length=500)
    required_inputs: str = Field(default="", max_length=500)
    produced_output: str = Field(default="", max_length=500)

    @field_validator("allowed_tools")
    @classmethod
    def clamp_allowed_tools(cls, value: list[str]) -> list[str]:
        return [item for item in value if item in WORKER_TOOL_ALLOWLIST]


class ResearchPlanWrite(BaseModel):
    strategy: str = Field(min_length=1, max_length=16000)
    success_criteria: str = Field(min_length=1, max_length=8000)
    questions: list[str] = Field(default_factory=list, max_length=50)
    tasks: list[PlannerTask] = Field(default_factory=list, max_length=50)


class PlannerQuestion(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    priority: int = Field(default=3, ge=1, le=5)


class PlannerStructuredTask(BaseModel):
    """Gemini-safe task slice. Domain PlannerTask applies stricter keys after repair."""

    task_key: str
    objective: str
    depends_on: list[str] = Field(default_factory=list)
    priority: int = 3
    dependency_reason: str = ""
    required_inputs: str = ""
    produced_output: str = ""


class DependencyValidatorTask(BaseModel):
    """Gemini-safe validator task. May split a false-simple plan into a chain."""

    task_key: str
    objective: str
    depends_on: list[str] = Field(default_factory=list)
    dependency_reason: str = ""
    parallel_safe: bool = True
    priority: int = 3


class DependencyValidatorOutput(BaseModel):
    """One bounded semantic pass. Not chain-of-thought; auditable DAG corrections only."""

    decomposition: str
    false_simple: bool = False
    notes: str = ""
    tasks: list[DependencyValidatorTask] = Field(default_factory=list)


class PlannerStructuredOutput(BaseModel):
    """Structured planner schema sent to providers. Avoid regex/pattern/optional-null fields."""

    approach: str
    success_criteria: str
    decomposition: str = "unspecified"
    questions: list[PlannerQuestion]
    tasks: list[PlannerStructuredTask] = Field(default_factory=list)


class PlannerOutput(BaseModel):
    """Structured planner output — no free-text parsing."""

    approach: str = Field(min_length=1, max_length=4000)
    success_criteria: str = Field(min_length=1, max_length=4000)
    decomposition: PlanDecomposition = PlanDecomposition.UNSPECIFIED
    questions: list[PlannerQuestion] = Field(default_factory=list, max_length=20)
    tasks: list[PlannerTask] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def fill_questions_from_tasks(self) -> "PlannerOutput":
        if not self.questions and self.tasks:
            self.questions = [
                PlannerQuestion(text=task.question_text or task.objective, priority=task.priority)
                for task in self.tasks
            ]
        if not self.questions:
            raise ValueError("planner output requires questions or tasks")
        return self


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
    extraction_metadata: dict[str, str | int | float | bool | list[str]] = Field(
        default_factory=dict
    )


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


class ReportSynthesisOutput(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    body_markdown: str = Field(min_length=1, max_length=200_000)
    cited_claim_ids: list[UUID] = Field(default_factory=list, max_length=50)
    limitations: str = Field(default="", max_length=8000)


class ReportWrite(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    body_markdown: str = Field(min_length=1, max_length=200_000)
    cited_evidence_ids: list[UUID] = Field(min_length=1)


class ResearchTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    goal: str = Field(min_length=1, max_length=8000)
    research_mode: Literal["quick", "standard", "deep"] = "standard"
    output_language: str = Field(default="en", min_length=2, max_length=16)


class ResearchTemplateRead(BaseModel):
    id: UUID
    name: str
    goal: str
    research_mode: Literal["quick", "standard", "deep"]
    output_language: str
    created_at: datetime
    updated_at: datetime


class FollowUpCreate(BaseModel):
    goal: str = Field(min_length=1, max_length=8000)
    inherit_source_preferences: bool = True
    research_mode: Literal["quick", "standard", "deep"] | None = None
    output_language: str | None = Field(default=None, max_length=16)


class SourcePreferenceWrite(BaseModel):
    action: Literal["pin", "exclude"]
    identity_kind: Literal["url", "domain"] = "url"
    identity_value: str = Field(min_length=1, max_length=2048)
    reason: str = Field(default="", max_length=500)


class SourcePreferenceRead(BaseModel):
    id: UUID
    research_run_id: UUID
    action: str
    identity_kind: str
    identity_value: str
    reason: str
    origin: str
    created_at: datetime


class ResearchMonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    goal: str = Field(min_length=1, max_length=8000)
    schedule_kind: Literal["daily", "weekly", "interval"] = "daily"
    timezone: str = Field(default="UTC", min_length=1, max_length=64)
    hour: int = Field(default=9, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    weekday: int = Field(default=0, ge=0, le=6)
    interval_minutes: int = Field(default=1440, ge=15, le=10080)
    research_mode: Literal["quick", "standard", "deep"] = "standard"
    template_id: UUID | None = None
    enabled: bool = True


class ResearchMonitorRead(BaseModel):
    id: UUID
    name: str
    goal: str
    schedule_kind: str
    timezone: str
    hour: int
    minute: int
    weekday: int
    interval_minutes: int
    enabled: bool
    status: str
    research_mode: str
    template_id: UUID | None = None
    last_run_id: UUID | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None
    last_success_at: datetime | None = None
    last_change_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WebVitalWrite(BaseModel):
    route: str = Field(min_length=1, max_length=128)
    lcp_ms: float | None = Field(default=None, ge=0, le=120_000)
    inp_ms: float | None = Field(default=None, ge=0, le=30_000)
    cls: float | None = Field(default=None, ge=0, le=10)
    ttfb_ms: float | None = Field(default=None, ge=0, le=60_000)
    fcp_ms: float | None = Field(default=None, ge=0, le=60_000)
    navigation_type: str = Field(default="navigate", max_length=32)
    device_class: str = Field(default="unknown", max_length=32)
    network_class: str = Field(default="unknown", max_length=32)
    source: Literal["field", "lab"] = "field"
