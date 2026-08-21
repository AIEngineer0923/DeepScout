"""SQLAlchemy ORM models for the research domain."""

import uuid
from datetime import datetime

from deepscout_core.domain.enums import (
    BudgetMetric,
    ClaimVerificationStatus,
    ContradictionEvidenceStatus,
    CostReportStatus,
    IndexingStatus,
    KnowledgeProvenanceKind,
    KnowledgeRelationType,
    ResearchJobStatus,
    ResearchJobType,
    ResearchQuestionStatus,
    ResearchRunStatus,
    ResearchTaskStatus,
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
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
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
    page_type: Mapped[WikiPageType] = mapped_column(pg_enum(WikiPageType, "wiki_page_type"), nullable=False)
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
    change_op: Mapped[WikiChangeOp] = mapped_column(pg_enum(WikiChangeOp, "wiki_change_op"), nullable=False)
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
    compiled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
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
    link_type: Mapped[WikiLinkType] = mapped_column(pg_enum(WikiLinkType, "wiki_link_type"), nullable=False)
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
