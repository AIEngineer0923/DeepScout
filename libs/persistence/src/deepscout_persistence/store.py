"""Focused persistence operations for the research domain."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from deepscout_core.domain.budget import (
    BudgetConsumption,
    BudgetExhaustedError,
    BudgetMetric,
    ResearchBudget,
)
from deepscout_core.domain.enums import (
    TERMINAL_RESEARCH_RUN_STATUSES,
    ClaimVerificationStatus,
    CostReportStatus,
    ResearchJobStatus,
    ResearchJobType,
    ResearchQuestionStatus,
    ResearchRunStatus,
    ResearchTaskStatus,
    UsageReportStatus,
)
from deepscout_core.domain.invariants import (
    assert_claim_verification_allowed,
    assert_contradiction_invariants,
    assert_decision_claims_are_verified,
    assert_evidence_has_snapshot,
    assert_question_status_transition,
    assert_report_has_evidence,
    assert_run_status_transition,
    assert_same_run,
)
from deepscout_core.domain.schemas import (
    ClaimWrite,
    ContradictionWrite,
    DecisionWrite,
    EvidenceWrite,
    ReportWrite,
    ResearchPlanWrite,
    ResearchQuestionRead,
    ResearchRunCreate,
    ResearchRunRead,
    ResearchTaskRead,
    SearchCandidateWrite,
    SourceSnapshotWrite,
    SourceWrite,
    ToolExecutionWrite,
)
from deepscout_core.domain.usage import RunUsageSummary, TokenUsageRecord
from deepscout_core.settings import Settings
from deepscout_providers.defaults import DEFAULT_CHAT_MODELS
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from deepscout_persistence.models import (
    BudgetLedgerEntryRow,
    ClaimRow,
    ContradictionRow,
    DecisionClaimRow,
    DecisionRow,
    EvidenceRow,
    ReportEvidenceRow,
    ReportRow,
    ResearchJobRow,
    ResearchPlanRow,
    ResearchQuestionRow,
    ResearchRunRow,
    ResearchTaskRow,
    RunEventRow,
    SearchCandidateRow,
    SourceRow,
    SourceSnapshotRow,
    TokenUsageRecordRow,
    ToolExecutionRow,
)


class ResearchStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_run(self, payload: ResearchRunCreate, settings: Settings) -> ResearchRunRead:
        budget = payload.budget or settings.default_research_budget()
        budget = _budget_for_mode(budget, payload.research_mode)
        provider = settings.llm_provider
        model = settings.llm_model or DEFAULT_CHAT_MODELS[provider]
        row = ResearchRunRow(
            goal=payload.goal,
            status=ResearchRunStatus.PENDING,
            llm_provider=provider.value,
            llm_model=model,
            research_mode=payload.research_mode,
            output_language=payload.output_language,
            max_iterations=budget.max_iterations,
            max_wall_time_seconds=budget.max_wall_time_seconds,
            max_total_tokens=budget.max_total_tokens,
            max_cost_usd=budget.max_cost_usd,
            max_sources=budget.max_sources,
            max_tool_calls=budget.max_tool_calls,
        )
        self._session.add(row)
        self._session.flush()
        return _run_to_read(row)

    def get_run(self, run_id: uuid.UUID) -> ResearchRunRead | None:
        row = self._session.get(ResearchRunRow, run_id)
        return _run_to_read(row) if row else None

    def get_run_row(self, run_id: uuid.UUID) -> ResearchRunRow | None:
        return self._session.get(ResearchRunRow, run_id)

    def list_runs(
        self,
        *,
        status: str | None = None,
        query: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ResearchRunRow], int]:
        stmt = select(ResearchRunRow)
        count_stmt = select(func.count()).select_from(ResearchRunRow)
        if status:
            try:
                enum_status = ResearchRunStatus(status)
            except ValueError as exc:
                raise ValueError(f"Invalid run status: {status}") from exc
            stmt = stmt.where(ResearchRunRow.status == enum_status)
            count_stmt = count_stmt.where(ResearchRunRow.status == enum_status)
        if query:
            like = f"%{query.strip()}%"
            stmt = stmt.where(ResearchRunRow.goal.ilike(like))
            count_stmt = count_stmt.where(ResearchRunRow.goal.ilike(like))
        total = int(self._session.scalar(count_stmt) or 0)
        rows = list(
            self._session.scalars(
                stmt.order_by(ResearchRunRow.created_at.desc()).limit(limit).offset(offset)
            ).all()
        )
        return rows, total

    def update_run_status(self, run_id: uuid.UUID, status: ResearchRunStatus) -> ResearchRunRead:
        row = self._require_run(run_id)
        assert_run_status_transition(current=row.status, new=status)
        row.status = status
        row.updated_at = datetime.now(UTC)
        if status == ResearchRunStatus.RUNNING and row.started_at is None:
            row.started_at = datetime.now(UTC)
        if status in {
            ResearchRunStatus.COMPLETED,
            ResearchRunStatus.FAILED,
            ResearchRunStatus.CANCELLED,
            ResearchRunStatus.BUDGET_EXHAUSTED,
        }:
            row.completed_at = datetime.now(UTC)
        self._session.flush()
        return _run_to_read(row)

    def save_plan(self, run_id: uuid.UUID, plan: ResearchPlanWrite) -> uuid.UUID:
        run = self._require_run(run_id)
        if run.plan is not None:
            raise ValueError("Research plan already exists for this run")
        plan_row = ResearchPlanRow(
            research_run_id=run_id,
            strategy=plan.strategy,
            success_criteria=plan.success_criteria,
        )
        self._session.add(plan_row)
        self._session.flush()
        for index, question_text in enumerate(plan.questions):
            self._session.add(
                ResearchQuestionRow(
                    plan_id=plan_row.id,
                    text=question_text,
                    sort_order=index,
                )
            )
        self._session.flush()
        question_by_text = {
            question.text: question.id
            for question in self._session.scalars(
                select(ResearchQuestionRow).where(ResearchQuestionRow.plan_id == plan_row.id)
            ).all()
        }
        for task in plan.tasks:
            question_id = None
            if task.question_text and task.question_text in question_by_text:
                question_id = question_by_text[task.question_text]
            self._session.add(
                ResearchTaskRow(
                    research_run_id=run_id,
                    question_id=question_id,
                    task_key=task.task_key,
                    objective=task.objective,
                    status=ResearchTaskStatus.PENDING,
                    priority=task.priority,
                    depends_on=list(task.depends_on),
                    allowed_tools=list(task.allowed_tools),
                )
            )
        self._session.flush()
        return plan_row.id

    def list_questions(self, run_id: uuid.UUID) -> list[ResearchQuestionRead]:
        self._require_run(run_id)
        questions = self._session.scalars(
            select(ResearchQuestionRow)
            .join(ResearchPlanRow, ResearchQuestionRow.plan_id == ResearchPlanRow.id)
            .where(ResearchPlanRow.research_run_id == run_id)
            .order_by(ResearchQuestionRow.sort_order)
        ).all()
        return [
            ResearchQuestionRead(
                id=question.id,
                text=question.text,
                status=question.status,
                sort_order=question.sort_order,
            )
            for question in questions
        ]

    def update_question_status(
        self,
        question_id: uuid.UUID,
        status: ResearchQuestionStatus,
    ) -> ResearchQuestionRow:
        question = self._session.get(ResearchQuestionRow, question_id)
        if question is None:
            raise LookupError(f"ResearchQuestion {question_id} not found")
        assert_question_status_transition(current=question.status, new=status)
        question.status = status
        self._session.flush()
        return question

    def add_search_candidates(
        self,
        run_id: uuid.UUID,
        payload: SearchCandidateWrite,
    ) -> list[SearchCandidateRow]:
        self._require_run(run_id)
        rows: list[SearchCandidateRow] = []
        for result in payload.results:
            existing = self._session.scalar(
                select(SearchCandidateRow).where(
                    SearchCandidateRow.research_run_id == run_id,
                    SearchCandidateRow.query == payload.query,
                    SearchCandidateRow.url == result.url,
                )
            )
            if existing is not None:
                rows.append(existing)
                continue
            row = SearchCandidateRow(
                research_run_id=run_id,
                question_id=payload.question_id,
                query=payload.query,
                provider=payload.provider,
                url=result.url,
                title=result.title,
                snippet=result.snippet,
                score=result.score,
            )
            self._session.add(row)
            rows.append(row)
        self._session.flush()
        return rows

    def add_source(self, run_id: uuid.UUID, source: SourceWrite) -> tuple[SourceRow, bool]:
        self._require_run(run_id)
        existing = self._session.scalar(
            select(SourceRow).where(
                SourceRow.research_run_id == run_id,
                SourceRow.canonical_url == source.canonical_url,
            )
        )
        if existing is not None:
            return existing, False
        row = SourceRow(
            research_run_id=run_id,
            canonical_url=source.canonical_url,
            title=source.title,
            domain=source.domain,
            source_type=source.source_type,
        )
        self._session.add(row)
        self._session.flush()
        return row, True

    def list_sources(self, run_id: uuid.UUID) -> list[SourceRow]:
        self._require_run(run_id)
        return list(
            self._session.scalars(
                select(SourceRow)
                .where(SourceRow.research_run_id == run_id)
                .order_by(SourceRow.created_at)
            ).all()
        )

    def list_sources_without_snapshot(
        self, run_id: uuid.UUID, *, limit: int = 5
    ) -> list[SourceRow]:
        self._require_run(run_id)
        rows = self._session.scalars(
            select(SourceRow)
            .outerjoin(SourceSnapshotRow, SourceSnapshotRow.source_id == SourceRow.id)
            .where(SourceRow.research_run_id == run_id, SourceSnapshotRow.id.is_(None))
            .limit(limit)
        ).all()
        return list(rows)

    def list_search_candidates(self, run_id: uuid.UUID) -> list[SearchCandidateRow]:
        self._require_run(run_id)
        return list(
            self._session.scalars(
                select(SearchCandidateRow)
                .where(SearchCandidateRow.research_run_id == run_id)
                .order_by(SearchCandidateRow.created_at)
            ).all()
        )

    def list_claims(self, run_id: uuid.UUID) -> list[ClaimRow]:
        self._require_run(run_id)
        return list(
            self._session.scalars(
                select(ClaimRow)
                .where(ClaimRow.research_run_id == run_id)
                .order_by(ClaimRow.created_at)
            ).all()
        )

    def find_claim(
        self,
        run_id: uuid.UUID,
        *,
        source_id: uuid.UUID,
        statement: str,
    ) -> ClaimRow | None:
        self._require_run(run_id)
        return self._session.scalar(
            select(ClaimRow).where(
                ClaimRow.research_run_id == run_id,
                ClaimRow.source_id == source_id,
                ClaimRow.statement == statement[:8000],
            )
        )

    def get_latest_snapshot_for_source(self, source_id: uuid.UUID) -> SourceSnapshotRow | None:
        return self._session.scalar(
            select(SourceSnapshotRow)
            .where(SourceSnapshotRow.source_id == source_id)
            .order_by(SourceSnapshotRow.retrieved_at.desc())
            .limit(1)
        )

    def get_snapshot(self, snapshot_id: uuid.UUID) -> SourceSnapshotRow | None:
        return self._session.get(SourceSnapshotRow, snapshot_id)

    def list_snapshots_for_run(self, run_id: uuid.UUID) -> list[SourceSnapshotRow]:
        sources = self.list_sources(run_id)
        snapshots: list[SourceSnapshotRow] = []
        for source in sources:
            snapshots.extend(
                self._session.scalars(
                    select(SourceSnapshotRow)
                    .where(SourceSnapshotRow.source_id == source.id)
                    .order_by(SourceSnapshotRow.retrieved_at.desc())
                ).all()
            )
        return snapshots

    def list_tool_executions(self, run_id: uuid.UUID) -> list[ToolExecutionRow]:
        self._require_run(run_id)
        return list(
            self._session.scalars(
                select(ToolExecutionRow)
                .where(ToolExecutionRow.research_run_id == run_id)
                .order_by(ToolExecutionRow.created_at.desc())
            ).all()
        )

    def list_jobs_for_run(self, run_id: uuid.UUID) -> list[ResearchJobRow]:
        self._require_run(run_id)
        return list(
            self._session.scalars(
                select(ResearchJobRow)
                .where(ResearchJobRow.research_run_id == run_id)
                .order_by(ResearchJobRow.created_at.desc())
            ).all()
        )

    def list_evidence_for_claim(self, claim_id: uuid.UUID) -> list[EvidenceRow]:
        return list(
            self._session.scalars(
                select(EvidenceRow)
                .where(EvidenceRow.claim_id == claim_id)
                .order_by(EvidenceRow.created_at)
            ).all()
        )

    def evidence_exists(self, claim_id: uuid.UUID, snapshot_id: uuid.UUID, quote: str) -> bool:
        existing = self._session.scalar(
            select(EvidenceRow.id).where(
                EvidenceRow.claim_id == claim_id,
                EvidenceRow.snapshot_id == snapshot_id,
                EvidenceRow.quote == quote[:16000],
            )
        )
        return existing is not None

    def list_evidence(self, run_id: uuid.UUID) -> list[EvidenceRow]:
        self._require_run(run_id)
        return list(
            self._session.scalars(
                select(EvidenceRow)
                .join(ClaimRow, EvidenceRow.claim_id == ClaimRow.id)
                .where(ClaimRow.research_run_id == run_id)
                .order_by(EvidenceRow.created_at)
            ).all()
        )

    def save_report_draft(
        self,
        run_id: uuid.UUID,
        *,
        title: str,
        body_markdown: str,
    ) -> ReportRow:
        self._require_run(run_id)
        existing = self._session.scalar(
            select(ReportRow).where(ReportRow.research_run_id == run_id)
        )
        if existing is not None:
            existing.title = title
            existing.body_markdown = body_markdown
            self._session.flush()
            return existing
        report = ReportRow(
            research_run_id=run_id,
            title=title,
            body_markdown=body_markdown,
        )
        self._session.add(report)
        self._session.flush()
        return report

    def add_snapshot(
        self, source_id: uuid.UUID, snapshot: SourceSnapshotWrite
    ) -> SourceSnapshotRow:
        source = self._session.get(SourceRow, source_id)
        if source is None:
            raise LookupError(f"Source {source_id} not found")
        content_hash = _hash_content(snapshot.content)
        existing = self._session.scalar(
            select(SourceSnapshotRow).where(
                SourceSnapshotRow.source_id == source_id,
                SourceSnapshotRow.content_hash == content_hash,
            )
        )
        if existing is not None:
            return existing
        row = SourceSnapshotRow(
            source_id=source_id,
            content_hash=content_hash,
            mime_type=snapshot.mime_type,
            byte_size=len(snapshot.content.encode("utf-8")),
            content_text=snapshot.content,
            retrieval_metadata=snapshot.retrieval_metadata or None,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def add_claim(self, run_id: uuid.UUID, claim: ClaimWrite) -> ClaimRow:
        self._require_run(run_id)
        row = ClaimRow(
            research_run_id=run_id,
            source_id=claim.source_id,
            question_id=claim.question_id,
            statement=claim.statement,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def attach_evidence(self, claim_id: uuid.UUID, evidence: EvidenceWrite) -> EvidenceRow:
        assert_evidence_has_snapshot(snapshot_id=evidence.snapshot_id)
        claim = self._session.get(ClaimRow, claim_id)
        if claim is None:
            raise LookupError(f"Claim {claim_id} not found")
        snapshot = self._session.get(SourceSnapshotRow, evidence.snapshot_id)
        if snapshot is None:
            raise LookupError(f"SourceSnapshot {evidence.snapshot_id} not found")
        snapshot_run_id = self._snapshot_run_id(snapshot.id)
        assert_same_run(
            expected_run_id=claim.research_run_id,
            actual_run_id=snapshot_run_id,
            entity="Evidence snapshot",
        )
        row = EvidenceRow(
            claim_id=claim_id,
            snapshot_id=evidence.snapshot_id,
            quote=evidence.quote,
            locator=evidence.locator,
            support_strength=evidence.support_strength,
            confidence=evidence.confidence,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def update_claim_verification(
        self,
        claim_id: uuid.UUID,
        status: ClaimVerificationStatus,
    ) -> ClaimRow:
        claim = self._session.get(ClaimRow, claim_id)
        if claim is None:
            raise LookupError(f"Claim {claim_id} not found")
        evidence_count = len(
            self._session.scalars(
                select(EvidenceRow.id).where(EvidenceRow.claim_id == claim_id)
            ).all()
        )
        assert_claim_verification_allowed(
            verification_status=status,
            evidence_count=evidence_count,
        )
        claim.verification_status = status
        self._session.flush()
        return claim

    def add_contradiction(self, run_id: uuid.UUID, payload: ContradictionWrite) -> ContradictionRow:
        self._require_run(run_id)
        claim_a = self._session.get(ClaimRow, payload.claim_a_id)
        claim_b = self._session.get(ClaimRow, payload.claim_b_id)
        if claim_a is None or claim_b is None:
            raise LookupError("One or both contradiction claims were not found")
        claim_a_evidence = len(claim_a.evidence_items)
        claim_b_evidence = len(claim_b.evidence_items)
        assert_contradiction_invariants(
            claim_a_id=payload.claim_a_id,
            claim_b_id=payload.claim_b_id,
            claim_a_run_id=claim_a.research_run_id,
            claim_b_run_id=claim_b.research_run_id,
            run_id=run_id,
            evidence_status=payload.evidence_status,
            claim_a_evidence_count=claim_a_evidence,
            claim_b_evidence_count=claim_b_evidence,
        )
        pair = {payload.claim_a_id, payload.claim_b_id}
        for existing in self._session.scalars(
            select(ContradictionRow).where(ContradictionRow.research_run_id == run_id)
        ).all():
            if {existing.claim_a_id, existing.claim_b_id} == pair:
                return existing
        row = ContradictionRow(
            research_run_id=run_id,
            claim_a_id=payload.claim_a_id,
            claim_b_id=payload.claim_b_id,
            description=payload.description,
            evidence_status=payload.evidence_status,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def list_contradictions(self, run_id: uuid.UUID) -> list[ContradictionRow]:
        self._require_run(run_id)
        return list(
            self._session.scalars(
                select(ContradictionRow)
                .where(ContradictionRow.research_run_id == run_id)
                .order_by(ContradictionRow.created_at)
            ).all()
        )

    def get_decision(self, run_id: uuid.UUID) -> DecisionRow | None:
        self._require_run(run_id)
        return self._session.scalar(
            select(DecisionRow).where(DecisionRow.research_run_id == run_id)
        )

    def cancel_run(self, run_id: uuid.UUID) -> ResearchRunRow:
        row = self._require_run(run_id)
        if row.status in TERMINAL_RESEARCH_RUN_STATUSES:
            return row
        row.status = ResearchRunStatus.CANCELLED
        row.termination_reason = "cancelled"
        row.updated_at = datetime.now(UTC)
        active_tasks = self._session.scalars(
            select(ResearchTaskRow).where(
                ResearchTaskRow.research_run_id == run_id,
                ResearchTaskRow.status.not_in(
                    {
                        ResearchTaskStatus.COMPLETED,
                        ResearchTaskStatus.FAILED,
                        ResearchTaskStatus.CANCELLED,
                    }
                ),
            )
        ).all()
        for task in active_tasks:
            task.status = ResearchTaskStatus.CANCELLED
            task.completed_at = datetime.now(UTC)
        self._session.flush()
        return row

    def save_tool_execution(
        self, run_id: uuid.UUID, payload: ToolExecutionWrite
    ) -> ToolExecutionRow:
        self._require_run(run_id)
        row = ToolExecutionRow(
            research_run_id=run_id,
            tool_name=payload.tool_name,
            input_summary=payload.input_summary,
            output_summary=payload.output_summary,
            status=payload.status,
            duration_ms=payload.duration_ms,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def save_decision(self, run_id: uuid.UUID, payload: DecisionWrite) -> DecisionRow:
        self._require_run(run_id)
        claims = self._session.scalars(
            select(ClaimRow).where(ClaimRow.id.in_(payload.supporting_claim_ids))
        ).all()
        if len(claims) != len(payload.supporting_claim_ids):
            raise LookupError("One or more supporting claims were not found")
        for claim in claims:
            assert_same_run(
                expected_run_id=run_id,
                actual_run_id=claim.research_run_id,
                entity="Decision supporting claim",
            )
        assert_decision_claims_are_verified(
            claim_statuses=[claim.verification_status for claim in claims]
        )
        decision = DecisionRow(
            research_run_id=run_id,
            recommendation=payload.recommendation,
            rationale=payload.rationale,
            confidence=payload.confidence,
        )
        self._session.add(decision)
        self._session.flush()
        for claim in claims:
            self._session.add(DecisionClaimRow(decision_id=decision.id, claim_id=claim.id))
        self._session.flush()
        return decision

    def save_report(self, run_id: uuid.UUID, payload: ReportWrite) -> ReportRow:
        assert_report_has_evidence(evidence_ids=payload.cited_evidence_ids)
        self._require_run(run_id)
        evidence_rows = self._session.scalars(
            select(EvidenceRow).where(EvidenceRow.id.in_(payload.cited_evidence_ids))
        ).all()
        if len(evidence_rows) != len(payload.cited_evidence_ids):
            raise LookupError("One or more cited evidence rows were not found")
        for evidence in evidence_rows:
            claim = evidence.claim
            assert_same_run(
                expected_run_id=run_id,
                actual_run_id=claim.research_run_id,
                entity="Report cited evidence",
            )
        report = ReportRow(
            research_run_id=run_id,
            title=payload.title,
            body_markdown=payload.body_markdown,
        )
        self._session.add(report)
        self._session.flush()
        for evidence in evidence_rows:
            self._session.add(ReportEvidenceRow(report_id=report.id, evidence_id=evidence.id))
        self._session.flush()
        return report

    def record_budget_usage(
        self,
        run_id: uuid.UUID,
        metric: BudgetMetric,
        delta: float,
        *,
        note: str = "",
    ) -> ResearchRunRow:
        row = self._session.execute(
            select(ResearchRunRow).where(ResearchRunRow.id == run_id).with_for_update()
        ).scalar_one()
        budget = _budget_from_run(row)
        consumption = _consumption_from_run(row)
        updated = _apply_budget_delta(consumption, metric, delta)
        if consumption.would_exceed(budget, metric, delta):
            raise BudgetExhaustedError(f"Budget exhausted for {metric.value}")
        _write_consumption_to_run(row, updated)
        self._session.add(
            BudgetLedgerEntryRow(
                research_run_id=run_id,
                metric=metric,
                delta=delta,
                note=note,
            )
        )
        self._session.flush()
        return row

    def get_consumption(self, run_id: uuid.UUID) -> BudgetConsumption:
        row = self._require_run(run_id)
        return _consumption_from_run(row)

    def set_termination_reason(self, run_id: uuid.UUID, reason: str) -> None:
        row = self._require_run(run_id)
        row.termination_reason = reason
        row.updated_at = datetime.now(UTC)
        self._session.flush()

    def list_tasks(self, run_id: uuid.UUID) -> list[ResearchTaskRead]:
        self._require_run(run_id)
        rows = self._session.scalars(
            select(ResearchTaskRow)
            .where(ResearchTaskRow.research_run_id == run_id)
            .order_by(ResearchTaskRow.priority, ResearchTaskRow.task_key)
        ).all()
        return [_task_to_read(row) for row in rows]

    def update_task_status(
        self,
        task_id: uuid.UUID,
        status: ResearchTaskStatus,
        *,
        worker_id: uuid.UUID | None = None,
        error_message: str | None = None,
    ) -> ResearchTaskRow:
        row = self._session.get(ResearchTaskRow, task_id)
        if row is None:
            raise LookupError(f"ResearchTask {task_id} not found")
        if row.status == ResearchTaskStatus.COMPLETED and status != ResearchTaskStatus.COMPLETED:
            return row
        if (
            worker_id is not None
            and row.worker_id is not None
            and row.worker_id != worker_id
        ):
            return row
        if (
            worker_id is not None
            and row.status
            in {ResearchTaskStatus.READY, ResearchTaskStatus.PENDING, ResearchTaskStatus.CANCELLED}
            and status in {ResearchTaskStatus.COMPLETED, ResearchTaskStatus.FAILED}
        ):
            return row
        row.status = status
        if worker_id is not None:
            row.worker_id = worker_id
        if error_message is not None:
            row.error_message = error_message[:4000]
        now = datetime.now(UTC)
        if status == ResearchTaskStatus.RUNNING and row.started_at is None:
            row.started_at = now
        if status in {
            ResearchTaskStatus.COMPLETED,
            ResearchTaskStatus.FAILED,
            ResearchTaskStatus.CANCELLED,
        }:
            row.completed_at = now
        self._session.flush()
        return row

    def claim_ready_task(self, task_id: uuid.UUID, worker_id: uuid.UUID) -> bool:
        """Atomically claim a READY task. Returns False if another worker won."""
        row = self._session.scalar(
            select(ResearchTaskRow)
            .where(
                ResearchTaskRow.id == task_id,
                ResearchTaskRow.status == ResearchTaskStatus.READY,
            )
            .with_for_update(skip_locked=True)
        )
        if row is None:
            return False
        row.status = ResearchTaskStatus.RUNNING
        row.worker_id = worker_id
        row.started_at = row.started_at or datetime.now(UTC)
        self._session.flush()
        return True

    def reclaim_stale_running_tasks(
        self, run_id: uuid.UUID, *, stale_after_seconds: int = 180
    ) -> int:
        """Return RUNNING tasks to READY after interruption, unless already finalized."""
        self._require_run(run_id)
        now = datetime.now(UTC)
        rows = list(
            self._session.scalars(
                select(ResearchTaskRow).where(
                    ResearchTaskRow.research_run_id == run_id,
                    ResearchTaskRow.status == ResearchTaskStatus.RUNNING,
                )
            ).all()
        )
        reclaimed = 0
        for row in rows:
            checkpoint = row.checkpoint or {}
            if (
                checkpoint.get("phase") == "research"
                and checkpoint.get("sources_added") is not None
            ):
                row.status = ResearchTaskStatus.COMPLETED
                row.completed_at = row.completed_at or now
                continue
            started = row.started_at or row.created_at
            if started is not None and (now - started).total_seconds() < stale_after_seconds:
                continue
            row.status = ResearchTaskStatus.READY
            row.worker_id = None
            row.error_message = "reclaimed_after_interruption"
            reclaimed += 1
        self._session.flush()
        return reclaimed

    def get_report(self, run_id: uuid.UUID) -> ReportRow | None:
        self._require_run(run_id)
        return self._session.scalar(select(ReportRow).where(ReportRow.research_run_id == run_id))

    def save_task_checkpoint(self, task_id: uuid.UUID, checkpoint: dict) -> None:
        row = self._session.get(ResearchTaskRow, task_id)
        if row is None:
            raise LookupError(f"ResearchTask {task_id} not found")
        row.checkpoint = checkpoint
        self._session.flush()

    def append_run_event(
        self,
        run_id: uuid.UUID,
        event_type: str,
        payload: dict | None = None,
    ) -> RunEventRow:
        self._require_run(run_id)
        next_sequence = self._session.scalar(
            select(func.coalesce(func.max(RunEventRow.sequence), 0)).where(
                RunEventRow.research_run_id == run_id
            )
        )
        row = RunEventRow(
            research_run_id=run_id,
            sequence=int(next_sequence or 0) + 1,
            event_type=event_type,
            payload=payload or {},
        )
        self._session.add(row)
        self._session.flush()
        return row

    def list_run_events(self, run_id: uuid.UUID, *, after_sequence: int = 0) -> list[RunEventRow]:
        self._require_run(run_id)
        return list(
            self._session.scalars(
                select(RunEventRow)
                .where(
                    RunEventRow.research_run_id == run_id,
                    RunEventRow.sequence > after_sequence,
                )
                .order_by(RunEventRow.sequence)
            ).all()
        )

    def record_token_usage(
        self,
        usage: TokenUsageRecord,
        *,
        pricing_version: str | None = None,
        cost_usd: float | None = None,
        cost_status: CostReportStatus | None = None,
    ) -> None:
        resolved_cost_status = cost_status or CostReportStatus.UNKNOWN
        row = TokenUsageRecordRow(
            research_run_id=usage.research_run_id,
            phase=usage.phase.value,
            agent_role=usage.agent_role.value,
            provider=usage.provider,
            model=usage.model,
            task_id=usage.task_id,
            worker_id=usage.worker_id,
            iteration=usage.iteration,
            retry=usage.retry,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            reasoning_tokens=usage.reasoning_tokens,
            total_tokens=usage.total_tokens,
            cost_usd=cost_usd,
            usage_report_status=usage.report_status,
            cost_report_status=resolved_cost_status,
            pricing_version=pricing_version,
        )
        self._session.add(row)
        run = self._require_run(usage.research_run_id)
        if usage.total_tokens is not None and usage.agent_role.value != "evaluator":
            current = run.consumed_total_tokens or 0
            run.consumed_total_tokens = current + usage.total_tokens
            run.usage_report_status = UsageReportStatus.PARTIAL
        if (
            usage.agent_role.value != "evaluator"
            and cost_usd is not None
            and resolved_cost_status != CostReportStatus.UNKNOWN
        ):
            run.consumed_cost_usd = float(run.consumed_cost_usd or 0.0) + float(cost_usd)
            run.pricing_version = pricing_version or run.pricing_version
            if run.cost_report_status == CostReportStatus.UNKNOWN:
                run.cost_report_status = resolved_cost_status
        self._session.flush()

    def get_usage_summary(self, run_id: uuid.UUID) -> RunUsageSummary:
        row = self._require_run(run_id)
        records = self._session.scalars(
            select(TokenUsageRecordRow).where(TokenUsageRecordRow.research_run_id == run_id)
        ).all()
        application = [record for record in records if record.agent_role != "evaluator"]
        evaluation = [record for record in records if record.agent_role == "evaluator"]

        def _sum(values: list[int | None]) -> int | None:
            known = [value for value in values if value is not None]
            return sum(known) if known else None

        def _cost(group: list[TokenUsageRecordRow]) -> tuple[float | None, CostReportStatus, str | None]:
            if not group:
                return None, CostReportStatus.UNKNOWN, "no_usage_records"
            unknown = [record for record in group if record.cost_report_status.value == "unknown"]
            known = [record.cost_usd for record in group if record.cost_usd is not None]
            if unknown:
                return None, CostReportStatus.UNKNOWN, "incomplete_token_split_or_unpriced_model"
            if not known:
                return None, CostReportStatus.UNKNOWN, "pricing_not_mapped"
            return sum(known), CostReportStatus.ESTIMATED, None

        app_cost, app_status, reason = _cost(application)
        eval_cost, _, eval_reason = _cost(evaluation)
        return RunUsageSummary(
            input_tokens=_sum([record.input_tokens for record in application]),
            output_tokens=_sum([record.output_tokens for record in application]),
            cached_input_tokens=_sum([record.cached_input_tokens for record in application]),
            reasoning_tokens=_sum([record.reasoning_tokens for record in application]),
            total_tokens=row.consumed_total_tokens,
            cost_usd=app_cost,
            usage_status=row.usage_report_status,
            cost_status=app_status,
            pricing_version=row.pricing_version,
            evaluation_total_tokens=_sum([record.total_tokens for record in evaluation]),
            evaluation_cost_usd=eval_cost if evaluation else None,
            cost_unknown_reason=reason if app_status == CostReportStatus.UNKNOWN else eval_reason,
        )

    def list_token_usage(self, run_id: uuid.UUID) -> list[TokenUsageRecordRow]:
        self._require_run(run_id)
        return list(
            self._session.scalars(
                select(TokenUsageRecordRow)
                .where(TokenUsageRecordRow.research_run_id == run_id)
                .order_by(TokenUsageRecordRow.created_at)
            ).all()
        )

    def enqueue_job(
        self,
        run_id: uuid.UUID,
        *,
        job_type: ResearchJobType,
        idempotency_key: str,
        payload: dict | None = None,
    ) -> ResearchJobRow:
        self._require_run(run_id)
        existing = self._session.scalar(
            select(ResearchJobRow).where(ResearchJobRow.idempotency_key == idempotency_key)
        )
        if existing is not None:
            return existing
        row = ResearchJobRow(
            research_run_id=run_id,
            job_type=job_type,
            status=ResearchJobStatus.PENDING,
            idempotency_key=idempotency_key,
            payload=payload or {},
        )
        self._session.add(row)
        self._session.flush()
        return row

    def claim_next_job(
        self, owner: str, *, lease_seconds: int, job_id: uuid.UUID | None = None
    ) -> ResearchJobRow | None:
        import secrets

        now = datetime.now(UTC)
        conditions = [
            ResearchJobRow.status.in_(
                [
                    ResearchJobStatus.PENDING,
                    ResearchJobStatus.CLAIMED,
                    ResearchJobStatus.RUNNING,
                ]
            ),
            (ResearchJobRow.lease_expires_at.is_(None))
            | (ResearchJobRow.lease_expires_at < now),
        ]
        if job_id is not None:
            conditions.append(ResearchJobRow.id == job_id)
        row = self._session.scalar(
            select(ResearchJobRow)
            .where(*conditions)
            .order_by(ResearchJobRow.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if row is None:
            return None
        row.status = ResearchJobStatus.RUNNING
        row.lease_owner = owner
        row.lease_token = secrets.token_hex(16)
        row.lease_expires_at = now + timedelta(seconds=lease_seconds)
        row.attempts += 1
        row.started_at = row.started_at or now
        row.updated_at = now
        self._session.flush()
        return row

    def renew_job_lease(
        self,
        job_id: uuid.UUID,
        *,
        owner: str,
        lease_token: str,
        lease_seconds: int,
    ) -> None:
        row = self._session.get(ResearchJobRow, job_id)
        if row is None or row.lease_owner != owner or row.lease_token != lease_token:
            raise LookupError("Invalid job lease")
        row.lease_expires_at = datetime.now(UTC) + timedelta(seconds=lease_seconds)
        row.updated_at = datetime.now(UTC)
        self._session.flush()

    def complete_job(self, job_id: uuid.UUID, *, owner: str, lease_token: str) -> None:
        row = self._session.get(ResearchJobRow, job_id)
        if row is None or row.lease_owner != owner or row.lease_token != lease_token:
            raise LookupError("Invalid job lease")
        row.status = ResearchJobStatus.COMPLETED
        row.completed_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)
        self._session.flush()

    def fail_job(
        self,
        job_id: uuid.UUID,
        *,
        owner: str,
        lease_token: str,
        error: str,
        retry: bool = True,
    ) -> None:
        row = self._session.get(ResearchJobRow, job_id)
        if row is None or row.lease_owner != owner or row.lease_token != lease_token:
            raise LookupError("Invalid job lease")
        row.last_error = error[:4000]
        row.updated_at = datetime.now(UTC)
        if retry and row.attempts < row.max_attempts:
            row.status = ResearchJobStatus.PENDING
            row.lease_owner = None
            row.lease_token = None
            row.lease_expires_at = None
        else:
            row.status = ResearchJobStatus.FAILED
            row.completed_at = datetime.now(UTC)
        self._session.flush()

    def recover_stale_jobs(self, now: datetime) -> int:
        rows = self._session.scalars(
            select(ResearchJobRow).where(
                ResearchJobRow.status == ResearchJobStatus.RUNNING,
                ResearchJobRow.lease_expires_at.is_not(None),
                ResearchJobRow.lease_expires_at < now,
            )
        ).all()
        for row in rows:
            row.status = ResearchJobStatus.PENDING
            row.lease_owner = None
            row.lease_token = None
            row.lease_expires_at = None
            row.updated_at = now
        self._session.flush()
        return len(rows)

    def _snapshot_run_id(self, snapshot_id: uuid.UUID) -> uuid.UUID:
        snapshot = self._session.get(SourceSnapshotRow, snapshot_id)
        if snapshot is None:
            raise LookupError(f"SourceSnapshot {snapshot_id} not found")
        source = self._session.get(SourceRow, snapshot.source_id)
        if source is None:
            raise LookupError(f"Source {snapshot.source_id} not found")
        return source.research_run_id

    def refresh(self) -> None:
        self._session.expire_all()

    def commit(self) -> None:
        self._session.commit()

    def get_concurrency_limit(self, run_id: uuid.UUID) -> int:
        return self._require_run(run_id).concurrency_limit

    def _require_run(self, run_id: uuid.UUID) -> ResearchRunRow:
        row = self._session.get(ResearchRunRow, run_id)
        if row is None:
            raise LookupError(f"ResearchRun {run_id} not found")
        return row


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _budget_for_mode(budget: ResearchBudget, mode: str | None) -> ResearchBudget:
    if mode == "quick":
        return ResearchBudget(
            max_iterations=min(2, budget.max_iterations),
            max_wall_time_seconds=min(300, budget.max_wall_time_seconds),
            max_total_tokens=min(40_000, budget.max_total_tokens),
            max_cost_usd=min(1.0, budget.max_cost_usd),
            max_sources=min(8, budget.max_sources),
            max_tool_calls=min(16, budget.max_tool_calls),
        )
    if mode == "deep":
        return ResearchBudget(
            max_iterations=max(5, budget.max_iterations),
            max_wall_time_seconds=max(budget.max_wall_time_seconds, 1200),
            max_total_tokens=max(budget.max_total_tokens, 400_000),
            max_cost_usd=max(budget.max_cost_usd, 8.0),
            max_sources=max(budget.max_sources, 60),
            max_tool_calls=max(budget.max_tool_calls, 120),
        )
    return budget


def _run_to_read(row: ResearchRunRow) -> ResearchRunRead:
    return ResearchRunRead(
        id=row.id,
        goal=row.goal,
        status=row.status,
        llm_provider=row.llm_provider,
        llm_model=row.llm_model,
        budget=_budget_from_run(row),
        usage=_usage_summary_from_run(row),
        termination_reason=row.termination_reason,
        research_mode=row.research_mode if row.research_mode in {"quick", "standard", "deep"} else None,
        output_language=row.output_language,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )


def _usage_summary_from_run(row: ResearchRunRow) -> RunUsageSummary:
    return RunUsageSummary(
        total_tokens=row.consumed_total_tokens,
        cost_usd=row.consumed_cost_usd if row.cost_report_status.value != "unknown" else None,
        usage_status=row.usage_report_status,
        cost_status=row.cost_report_status,
        pricing_version=row.pricing_version,
    )


def _task_to_read(row: ResearchTaskRow) -> ResearchTaskRead:
    return ResearchTaskRead(
        id=row.id,
        task_key=row.task_key,
        objective=row.objective,
        status=row.status,
        priority=row.priority,
        depends_on=list(row.depends_on or []),
        allowed_tools=list(row.allowed_tools or []),
        question_id=row.question_id,
        worker_id=row.worker_id,
        started_at=row.started_at,
        completed_at=row.completed_at,
        retry_count=row.retry_count,
    )


def _budget_from_run(row: ResearchRunRow) -> ResearchBudget:
    return ResearchBudget(
        max_iterations=row.max_iterations,
        max_wall_time_seconds=row.max_wall_time_seconds,
        max_total_tokens=row.max_total_tokens,
        max_cost_usd=row.max_cost_usd,
        max_sources=row.max_sources,
        max_tool_calls=row.max_tool_calls,
    )


def _consumption_from_run(row: ResearchRunRow) -> BudgetConsumption:
    return BudgetConsumption(
        iterations=row.consumed_iterations,
        wall_time_seconds=row.consumed_wall_time_seconds,
        total_tokens=row.consumed_total_tokens,
        cost_usd=row.consumed_cost_usd,
        sources=row.consumed_sources,
        tool_calls=row.consumed_tool_calls,
    )


def _apply_budget_delta(
    consumption: BudgetConsumption,
    metric: BudgetMetric,
    delta: float,
) -> BudgetConsumption:
    total_tokens = consumption.total_tokens
    if metric == BudgetMetric.TOKENS:
        total_tokens = int(delta) if total_tokens is None else total_tokens + int(delta)
    cost_usd = consumption.cost_usd
    if metric == BudgetMetric.COST:
        cost_usd = delta if cost_usd is None else cost_usd + delta
    return BudgetConsumption(
        iterations=consumption.iterations + int(delta)
        if metric == BudgetMetric.ITERATIONS
        else consumption.iterations,
        wall_time_seconds=consumption.wall_time_seconds + int(delta)
        if metric == BudgetMetric.WALL_TIME
        else consumption.wall_time_seconds,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        sources=consumption.sources + int(delta)
        if metric == BudgetMetric.SOURCES
        else consumption.sources,
        tool_calls=consumption.tool_calls + int(delta)
        if metric == BudgetMetric.TOOL_CALLS
        else consumption.tool_calls,
    )


def _write_consumption_to_run(row: ResearchRunRow, consumption: BudgetConsumption) -> None:
    row.consumed_iterations = consumption.iterations
    row.consumed_wall_time_seconds = consumption.wall_time_seconds
    row.consumed_total_tokens = consumption.total_tokens
    row.consumed_cost_usd = consumption.cost_usd
    row.consumed_sources = consumption.sources
    row.consumed_tool_calls = consumption.tool_calls
    row.updated_at = datetime.now(UTC)
