"""SQLAlchemy ORM models for the research domain."""

import uuid
from datetime import datetime

from deepscout_core.domain.enums import (
    AgentNoteKind,
    BudgetMetric,
    ClaimVerificationStatus,
    ContradictionEvidenceStatus,
    CostReportStatus,
    HumanFeedbackTarget,
    IndexingStatus,
    KnowledgeProvenanceKind,
    KnowledgeRelationType,
    ResearchJobStatus,
    ResearchJobType,
    ResearchQuestionStatus,
    ResearchRunStatus,
    ResearchTaskStatus,
    ReviewDecisionKind,
    ReviewReasonCode,
    ReviewRequestStatus,
    ReviewRiskLevel,
    SourceType,
    ToolExecutionStatus,
    UsageReportStatus,
    WikiChangeOp,
    WikiLinkType,
    WikiPageStatus,
    WikiPageType,
    WikiStatementStatus,
)
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from deepscout_persistence.base import Base, pg_enum


class ResearchRunRow(Base):
    __tablename__ = "research_runs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ResearchRunStatus] = mapped_column(
        pg_enum(ResearchRunStatus, "research_run_status"),
        nullable=False,
        default=ResearchRunStatus.PENDING,
    )
    llm_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    llm_model: Mapped[str] = mapped_column(String(128), nullable=False)
    research_mode: Mapped[str | None] = mapped_column(String(16))
    output_language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False)
    max_wall_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    max_total_tokens: Mapped[int] = mapped_column(Integer, nullable=False)
    max_cost_usd: Mapped[float] = mapped_column(Float, nullable=False)
    max_sources: Mapped[int] = mapped_column(Integer, nullable=False)
    max_tool_calls: Mapped[int] = mapped_column(Integer, nullable=False)
    consumed_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumed_wall_time_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumed_total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    consumed_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    consumed_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consumed_tool_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    termination_reason: Mapped[str | None] = mapped_column(String(64))
    concurrency_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    usage_report_status: Mapped[UsageReportStatus] = mapped_column(
        pg_enum(UsageReportStatus, "usage_report_status"),
        nullable=False,
        default=UsageReportStatus.UNKNOWN,
    )
    cost_report_status: Mapped[CostReportStatus] = mapped_column(
        pg_enum(CostReportStatus, "cost_report_status"),
        nullable=False,
        default=CostReportStatus.UNKNOWN,
    )
    pricing_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    config_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    parent_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="SET NULL")
    )
    fork_reason: Mapped[str | None] = mapped_column(String(128))
    replans_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    root_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="SET NULL")
    )
    monitor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_monitors.id", ondelete="SET NULL")
    )
    lineage_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    owner_principal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("principals.id", ondelete="RESTRICT")
    )
    is_public_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    public_slug: Mapped[str | None] = mapped_column(String(80), unique=True)

    plan: Mapped["ResearchPlanRow | None"] = relationship(back_populates="run", uselist=False)
    sources: Mapped[list["SourceRow"]] = relationship(back_populates="run")
    claims: Mapped[list["ClaimRow"]] = relationship(back_populates="run")
    ledger_entries: Mapped[list["BudgetLedgerEntryRow"]] = relationship(back_populates="run")


class ResearchPlanRow(Base):
    __tablename__ = "research_plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE"), unique=True
    )
    strategy: Mapped[str] = mapped_column(Text, nullable=False)
    success_criteria: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[ResearchRunRow] = relationship(back_populates="plan")
    questions: Mapped[list["ResearchQuestionRow"]] = relationship(back_populates="plan")


class ResearchQuestionRow(Base):
    __tablename__ = "research_questions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_plans.id", ondelete="CASCADE")
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ResearchQuestionStatus] = mapped_column(
        pg_enum(ResearchQuestionStatus, "research_question_status"),
        nullable=False,
        default=ResearchQuestionStatus.PENDING,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    plan: Mapped[ResearchPlanRow] = relationship(back_populates="questions")


class SourceRow(Base):
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint("research_run_id", "canonical_url", name="uq_sources_run_url"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    domain: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    source_type: Mapped[SourceType] = mapped_column(
        pg_enum(SourceType, "source_type"), nullable=False, default=SourceType.WEB
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[ResearchRunRow] = relationship(back_populates="sources")
    snapshots: Mapped[list["SourceSnapshotRow"]] = relationship(back_populates="source")


class SourceSnapshotRow(Base):
    __tablename__ = "source_snapshots"
    __table_args__ = (
        UniqueConstraint("source_id", "content_hash", name="uq_snapshots_source_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE")
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    mime_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    retrieval_metadata: Mapped[dict | None] = mapped_column(JSONB)
    indexing_status: Mapped[IndexingStatus] = mapped_column(
        pg_enum(IndexingStatus, "indexing_status"),
        nullable=False,
        default=IndexingStatus.PENDING,
    )
    indexing_error: Mapped[str | None] = mapped_column(Text)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    embedding_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunking_version: Mapped[str | None] = mapped_column(String(64))
    embedding_spec_key: Mapped[str | None] = mapped_column(String(256))
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source: Mapped[SourceRow] = relationship(back_populates="snapshots")
    evidence_items: Mapped[list["EvidenceRow"]] = relationship(back_populates="snapshot")
    chunks: Mapped[list["DocumentChunkRow"]] = relationship(back_populates="snapshot")


class ClaimRow(Base):
    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL")
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_questions.id", ondelete="SET NULL")
    )
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    verification_status: Mapped[ClaimVerificationStatus] = mapped_column(
        pg_enum(ClaimVerificationStatus, "claim_verification_status"),
        nullable=False,
        default=ClaimVerificationStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped[ResearchRunRow] = relationship(back_populates="claims")
    evidence_items: Mapped[list["EvidenceRow"]] = relationship(back_populates="claim")


class EvidenceRow(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE")
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_snapshots.id", ondelete="RESTRICT")
    )
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    support_strength: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    extraction_metadata: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    claim: Mapped[ClaimRow] = relationship(back_populates="evidence_items")
    snapshot: Mapped[SourceSnapshotRow] = relationship(back_populates="evidence_items")


class ContradictionRow(Base):
    __tablename__ = "contradictions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    claim_a_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE")
    )
    claim_b_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE")
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_status: Mapped[ContradictionEvidenceStatus] = mapped_column(
        pg_enum(ContradictionEvidenceStatus, "contradiction_evidence_status"),
        nullable=False,
        default=ContradictionEvidenceStatus.SUFFICIENT,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SearchCandidateRow(Base):
    __tablename__ = "search_candidates"
    __table_args__ = (
        UniqueConstraint(
            "research_run_id",
            "query",
            "url",
            name="uq_search_candidates_run_query_url",
        ),
        Index("ix_search_candidates_run_id", "research_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_questions.id", ondelete="SET NULL")
    )
    query: Mapped[str] = mapped_column(String(512), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    snippet: Mapped[str] = mapped_column(Text, nullable=False, default="")
    score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ToolExecutionRow(Base):
    __tablename__ = "tool_executions"
    __table_args__ = (Index("ix_tool_executions_run_id", "research_run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    tool_name: Mapped[str] = mapped_column(String(128), nullable=False)
    input_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    output_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[ToolExecutionStatus] = mapped_column(
        pg_enum(ToolExecutionStatus, "tool_execution_status"),
        nullable=False,
    )
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecisionRow(Base):
    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE"), unique=True
    )
    recommendation: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DecisionClaimRow(Base):
    __tablename__ = "decision_claims"
    __table_args__ = (UniqueConstraint("decision_id", "claim_id", name="uq_decision_claim"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    decision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("decisions.id", ondelete="CASCADE")
    )
    claim_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id", ondelete="CASCADE")
    )


class ReportRow(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE"), unique=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReportEvidenceRow(Base):
    __tablename__ = "report_evidence"
    __table_args__ = (UniqueConstraint("report_id", "evidence_id", name="uq_report_evidence"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("reports.id", ondelete="CASCADE")
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("evidence.id", ondelete="CASCADE")
    )


class BudgetLedgerEntryRow(Base):
    __tablename__ = "budget_ledger_entries"
    __table_args__ = (Index("ix_budget_ledger_run_id", "research_run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    metric: Mapped[BudgetMetric] = mapped_column(
        pg_enum(BudgetMetric, "budget_metric"), nullable=False
    )
    delta: Mapped[float] = mapped_column(Float, nullable=False)
    note: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    run: Mapped[ResearchRunRow] = relationship(back_populates="ledger_entries")


class ResearchTaskRow(Base):
    __tablename__ = "research_tasks"
    __table_args__ = (
        UniqueConstraint("research_run_id", "task_key", name="uq_research_tasks_run_key"),
        Index("ix_research_tasks_run_id", "research_run_id"),
        Index("ix_research_tasks_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    question_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_questions.id", ondelete="SET NULL")
    )
    task_key: Mapped[str] = mapped_column(String(64), nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ResearchTaskStatus] = mapped_column(
        pg_enum(ResearchTaskStatus, "research_task_status"),
        nullable=False,
        default=ResearchTaskStatus.PENDING,
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    depends_on: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    allowed_tools: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    model_policy: Mapped[dict | None] = mapped_column(JSONB)
    delegated_budget: Mapped[dict | None] = mapped_column(JSONB)
    worker_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    error_message: Mapped[str | None] = mapped_column(Text)
    checkpoint: Mapped[dict | None] = mapped_column(JSONB)
    task_meta: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchJobRow(Base):
    __tablename__ = "research_jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_research_jobs_idempotency"),
        Index("ix_research_jobs_status", "status"),
        Index("ix_research_jobs_run_id", "research_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    job_type: Mapped[ResearchJobType] = mapped_column(
        pg_enum(ResearchJobType, "research_job_type"), nullable=False
    )
    status: Mapped[ResearchJobStatus] = mapped_column(
        pg_enum(ResearchJobStatus, "research_job_status"),
        nullable=False,
        default=ResearchJobStatus.PENDING,
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    lease_token: Mapped[str | None] = mapped_column(String(64))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RunEventRow(Base):
    __tablename__ = "run_events"
    __table_args__ = (
        UniqueConstraint("research_run_id", "sequence", name="uq_run_events_run_sequence"),
        Index("ix_run_events_run_id", "research_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TokenUsageRecordRow(Base):
    __tablename__ = "token_usage_records"
    __table_args__ = (Index("ix_token_usage_records_run_id", "research_run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    agent_role: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_tasks.id", ondelete="SET NULL")
    )
    worker_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    iteration: Mapped[int | None] = mapped_column(Integer)
    retry: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    total_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[float | None] = mapped_column(Float)
    usage_report_status: Mapped[UsageReportStatus] = mapped_column(
        pg_enum(UsageReportStatus, "usage_report_status"),
        nullable=False,
        default=UsageReportStatus.UNKNOWN,
    )
    cost_report_status: Mapped[CostReportStatus] = mapped_column(
        pg_enum(CostReportStatus, "cost_report_status"),
        nullable=False,
        default=CostReportStatus.UNKNOWN,
    )
    pricing_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DocumentChunkRow(Base):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "source_snapshot_id",
            "chunking_version",
            "ordinal",
            name="uq_chunks_snapshot_version_ord",
        ),
        Index("ix_document_chunks_run_id", "research_run_id"),
        Index("ix_document_chunks_snapshot_id", "source_snapshot_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE")
    )
    source_snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("source_snapshots.id", ondelete="CASCADE")
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    context_text: Mapped[str | None] = mapped_column(Text)
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    section_title: Mapped[str | None] = mapped_column(String(200))
    chunking_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    snapshot: Mapped[SourceSnapshotRow] = relationship(back_populates="chunks")
    embeddings: Mapped[list["ChunkEmbeddingRow"]] = relationship(back_populates="chunk")


class ChunkEmbeddingRow(Base):
    __tablename__ = "chunk_embeddings"
    __table_args__ = (
        UniqueConstraint(
            "chunk_id",
            "provider",
            "model",
            "dimensions",
            "config_version",
            name="uq_chunk_embedding_space",
        ),
        Index("ix_chunk_embeddings_run_id", "research_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE")
    )
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    config_version: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunk: Mapped[DocumentChunkRow] = relationship(back_populates="embeddings")


class WikiPageRow(Base):
    __tablename__ = "wiki_pages"
    __table_args__ = (
        UniqueConstraint("research_run_id", "slug", name="uq_wiki_pages_run_slug"),
        Index("ix_wiki_pages_run_id", "research_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    page_type: Mapped[WikiPageType] = mapped_column(
        pg_enum(WikiPageType, "wiki_page_type"), nullable=False
    )
    status: Mapped[WikiPageStatus] = mapped_column(
        pg_enum(WikiPageStatus, "wiki_page_status"),
        nullable=False,
        default=WikiPageStatus.ACTIVE,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    revisions: Mapped[list["WikiRevisionRow"]] = relationship(back_populates="page")
    statements: Mapped[list["WikiStatementRow"]] = relationship(back_populates="page")


class WikiRevisionRow(Base):
    __tablename__ = "wiki_revisions"
    __table_args__ = (UniqueConstraint("page_id", "revision", name="uq_wiki_revisions_page_rev"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="CASCADE")
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    change_op: Mapped[WikiChangeOp] = mapped_column(
        pg_enum(WikiChangeOp, "wiki_change_op"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    page: Mapped[WikiPageRow] = relationship(back_populates="revisions")


class WikiStatementRow(Base):
    __tablename__ = "wiki_statements"
    __table_args__ = (
        Index("ix_wiki_statements_run_id", "research_run_id"),
        Index("ix_wiki_statements_claim_id", "claim_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="CASCADE")
    )
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    statement_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[WikiStatementStatus] = mapped_column(
        pg_enum(WikiStatementStatus, "wiki_statement_status"),
        nullable=False,
        default=WikiStatementStatus.ACTIVE,
    )
    claim_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id", ondelete="RESTRICT")
    )
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("evidence.id", ondelete="RESTRICT")
    )
    compiled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    page: Mapped[WikiPageRow] = relationship(back_populates="statements")


class WikiLinkRow(Base):
    __tablename__ = "wiki_links"
    __table_args__ = (
        UniqueConstraint("from_page_id", "to_page_id", "link_type", name="uq_wiki_links_edge"),
        Index("ix_wiki_links_run_id", "research_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    from_page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="CASCADE")
    )
    to_page_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("wiki_pages.id", ondelete="CASCADE")
    )
    link_type: Mapped[WikiLinkType] = mapped_column(
        pg_enum(WikiLinkType, "wiki_link_type"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class KnowledgeRelationRow(Base):
    __tablename__ = "knowledge_relations"
    __table_args__ = (Index("ix_knowledge_relations_run_id", "research_run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    from_statement_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("wiki_statements.id", ondelete="CASCADE")
    )
    to_statement_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("wiki_statements.id", ondelete="CASCADE")
    )
    relation_type: Mapped[KnowledgeRelationType] = mapped_column(
        pg_enum(KnowledgeRelationType, "knowledge_relation_type"), nullable=False
    )
    provenance_kind: Mapped[KnowledgeProvenanceKind] = mapped_column(
        pg_enum(KnowledgeProvenanceKind, "knowledge_provenance_kind"), nullable=False
    )
    claim_a_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id", ondelete="SET NULL")
    )
    claim_b_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("claims.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReviewRequestRow(Base):
    __tablename__ = "review_requests"
    __table_args__ = (
        Index("ix_review_requests_run_id", "research_run_id"),
        Index("ix_review_requests_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    research_task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    reason_code: Mapped[ReviewReasonCode] = mapped_column(
        pg_enum(ReviewReasonCode, "review_reason_code"), nullable=False
    )
    risk_level: Mapped[ReviewRiskLevel] = mapped_column(
        pg_enum(ReviewRiskLevel, "review_risk_level"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    proposed_action_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[ReviewRequestStatus] = mapped_column(
        pg_enum(ReviewRequestStatus, "review_request_status"),
        nullable=False,
        default=ReviewRequestStatus.PENDING,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False, default="hitl-v1")
    created_by_component: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resolved_by: Mapped[str | None] = mapped_column(String(128))
    resolved_source: Mapped[str | None] = mapped_column(String(32))
    decision_kind: Mapped[ReviewDecisionKind | None] = mapped_column(
        pg_enum(ReviewDecisionKind, "review_decision_kind")
    )
    decision_payload: Mapped[dict | None] = mapped_column(JSONB)
    decision_reason: Mapped[str | None] = mapped_column(Text)
    rejection_outcome: Mapped[str | None] = mapped_column(String(64))


class ReviewEventRow(Base):
    __tablename__ = "review_events"
    __table_args__ = (Index("ix_review_events_review_id", "review_request_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    review_request_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("review_requests.id", ondelete="CASCADE")
    )
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    actor_source: Mapped[str] = mapped_column(String(32), nullable=False)
    actor_identity: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class HumanFeedbackRow(Base):
    __tablename__ = "human_feedback"
    __table_args__ = (Index("ix_human_feedback_run_id", "research_run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    target_type: Mapped[HumanFeedbackTarget] = mapped_column(
        pg_enum(HumanFeedbackTarget, "human_feedback_target"), nullable=False
    )
    target_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    scores: Mapped[dict] = mapped_column(JSONB, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="ui")
    created_by: Mapped[str] = mapped_column(String(128), nullable=False, default="local_operator")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentNoteRow(Base):
    __tablename__ = "agent_notes"
    __table_args__ = (Index("ix_agent_notes_run_id", "research_run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    research_task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    kind: Mapped[AgentNoteKind] = mapped_column(
        pg_enum(AgentNoteKind, "agent_note_kind"), nullable=False
    )
    body: Mapped[str] = mapped_column(String(2000), nullable=False)
    artifact_ref: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RunSkillBindingRow(Base):
    __tablename__ = "run_skill_bindings"
    __table_args__ = (Index("ix_run_skill_bindings_run_id", "research_run_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    research_task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    skill_id: Mapped[str] = mapped_column(String(64), nullable=False)
    skill_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ContextCompactionRecordRow(Base):
    __tablename__ = "context_compaction_records"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    chars_before: Mapped[int] = mapped_column(Integer, nullable=False)
    chars_after: Mapped[int] = mapped_column(Integer, nullable=False)
    dropped_redundant: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    artifact_refs_kept: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchTemplateRow(Base):
    """Local MODE A saved research presets. Not accounts or sharing."""

    __tablename__ = "research_templates"
    __table_args__ = (Index("ix_research_templates_updated_at", "updated_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    research_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    output_language: Mapped[str] = mapped_column(String(16), nullable=False, default="en")
    owner_principal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("principals.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ResearchSourcePreferenceRow(Base):
    __tablename__ = "research_source_preferences"
    __table_args__ = (
        UniqueConstraint(
            "research_run_id",
            "action",
            "identity_kind",
            "identity_value",
            name="uq_source_pref_run_identity",
        ),
        Index("ix_source_preferences_run_id", "research_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE")
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    identity_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    identity_value: Mapped[str] = mapped_column(String(2048), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ResearchMonitorRow(Base):
    __tablename__ = "research_monitors"
    __table_args__ = (
        Index("ix_research_monitors_next_run_at", "next_run_at"),
        Index("ix_research_monitors_enabled", "enabled"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    schedule_kind: Mapped[str] = mapped_column(String(16), nullable=False, default="daily")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    hour: Mapped[int] = mapped_column(Integer, nullable=False, default=9)
    minute: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=1440)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    research_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_templates.id", ondelete="SET NULL")
    )
    last_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="SET NULL")
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_change_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(String(128))
    owner_principal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("principals.id", ondelete="RESTRICT")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WebVitalSampleRow(Base):
    __tablename__ = "web_vital_samples"
    __table_args__ = (
        Index("ix_web_vital_samples_created_at", "created_at"),
        Index("ix_web_vital_samples_route", "route"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    route: Mapped[str] = mapped_column(String(128), nullable=False)
    lcp_ms: Mapped[float | None] = mapped_column(Float)
    inp_ms: Mapped[float | None] = mapped_column(Float)
    cls: Mapped[float | None] = mapped_column(Float)
    ttfb_ms: Mapped[float | None] = mapped_column(Float)
    fcp_ms: Mapped[float | None] = mapped_column(Float)
    navigation_type: Mapped[str] = mapped_column(String(32), nullable=False, default="navigate")
    device_class: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    network_class: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="field")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PrincipalRow(Base):
    __tablename__ = "principals"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    email: Mapped[str | None] = mapped_column(String(320))
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    avatar_url: Mapped[str | None] = mapped_column(String(2048))
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuthAccountRow(Base):
    __tablename__ = "auth_accounts"
    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_account_id", name="uq_auth_accounts_provider_subject"
        ),
        Index("ix_auth_accounts_principal_id", "principal_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    principal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("principals.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SessionRow(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("ix_auth_sessions_principal_id", "principal_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    principal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("principals.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OAuthStateRow(Base):
    __tablename__ = "oauth_states"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    next_path: Mapped[str] = mapped_column(String(256), nullable=False, default="/")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ProviderCredentialRow(Base):
    __tablename__ = "provider_credentials"
    __table_args__ = (
        UniqueConstraint(
            "principal_id", "provider", name="uq_provider_credentials_principal_provider"
        ),
        Index("ix_provider_credentials_principal_id", "principal_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    principal_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("principals.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="configured")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AuthEventRow(Base):
    __tablename__ = "auth_events"
    __table_args__ = (Index("ix_auth_events_principal_id", "principal_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    principal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("principals.id", ondelete="SET NULL")
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EvaluationResultRow(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        UniqueConstraint("research_run_id", "evaluator_id", name="uq_evaluation_results_run_evaluator"),
        Index("ix_evaluation_results_run_id", "research_run_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False
    )
    evaluator_id: Mapped[str] = mapped_column(String(128), nullable=False)
    evaluator_version: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    value: Mapped[dict | list | str | int | float | bool | None] = mapped_column(JSONB)
    reason: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    method: Mapped[str] = mapped_column(String(64), nullable=False)
    applicability: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearningCaseRow(Base):
    __tablename__ = "learning_cases"
    __table_args__ = (
        UniqueConstraint("case_key", "owner_principal_id", name="uq_learning_cases_key_owner"),
        Index("ix_learning_cases_owner", "owner_principal_id"),
        Index("ix_learning_cases_review_state", "review_state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_key: Mapped[str] = mapped_column(String(128), nullable=False)
    owner_principal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("principals.id", ondelete="CASCADE")
    )
    research_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("research_runs.id", ondelete="SET NULL")
    )
    subsystem: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_class: Mapped[str] = mapped_column(String(64), nullable=False)
    symptom: Mapped[str] = mapped_column(Text, nullable=False)
    expected_behavior: Mapped[str] = mapped_column(Text, nullable=False, default="")
    observed_behavior: Mapped[str] = mapped_column(Text, nullable=False, default="")
    origin: Mapped[str] = mapped_column(String(64), nullable=False)
    trust_level: Mapped[str] = mapped_column(String(64), nullable=False)
    review_state: Mapped[str] = mapped_column(String(64), nullable=False)
    sanitized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    human_reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    root_cause_class: Mapped[str | None] = mapped_column(String(64))
    is_root_cause: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    downstream_symptom_of: Mapped[str | None] = mapped_column(String(128))
    diagnostic_evidence: Mapped[dict | None] = mapped_column(JSONB)
    evaluator_signals: Mapped[dict | None] = mapped_column(JSONB)
    affected_requirements: Mapped[list | None] = mapped_column(JSONB)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="medium")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    reproducibility: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    architecture_version: Mapped[str] = mapped_column(String(32), nullable=False, default="learning-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ImprovementCandidateRow(Base):
    __tablename__ = "improvement_candidates"
    __table_args__ = (
        Index("ix_improvement_candidates_case", "learning_case_id"),
        Index("ix_improvement_candidates_owner", "owner_principal_id"),
        Index("ix_improvement_candidates_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    candidate_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    learning_case_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("learning_cases.id", ondelete="CASCADE"), nullable=False
    )
    owner_principal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("principals.id", ondelete="CASCADE")
    )
    candidate_type: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    policy_delta: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    expected_benefit: Mapped[str] = mapped_column(Text, nullable=False, default="")
    possible_regressions: Mapped[str] = mapped_column(Text, nullable=False, default="")
    affected_subsystem: Mapped[str] = mapped_column(String(32), nullable=False)
    evaluation_plan: Mapped[dict | None] = mapped_column(JSONB)
    supporting_case_ids: Mapped[list | None] = mapped_column(JSONB)
    trust_level: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    rollback_info: Mapped[dict | None] = mapped_column(JSONB)
    experiment_result: Mapped[dict | None] = mapped_column(JSONB)
    promotion_verdict: Mapped[str | None] = mapped_column(String(64))
    promotion_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LearningPolicyVersionRow(Base):
    __tablename__ = "learning_policy_versions"
    __table_args__ = (
        Index("ix_learning_policy_versions_key", "policy_key"),
        Index("ix_learning_policy_versions_active", "active"),
        Index("ix_learning_policy_versions_owner", "owner_principal_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_key: Mapped[str] = mapped_column(String(128), nullable=False)
    version_label: Mapped[str] = mapped_column(String(64), nullable=False)
    owner_principal_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("principals.id", ondelete="CASCADE")
    )
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    promoted_from_candidate_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    promotion_reason: Mapped[str | None] = mapped_column(Text)
    evidence: Mapped[dict | None] = mapped_column(JSONB)
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
