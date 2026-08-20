"""Focused persistence operations for the research domain."""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime

from deepscout_core.domain.budget import (
    BudgetConsumption,
    BudgetExhaustedError,
    BudgetMetric,
    ResearchBudget,
)
from deepscout_core.domain.enums import (
    ClaimVerificationStatus,
    ResearchQuestionStatus,
    ResearchRunStatus,
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
    SearchCandidateWrite,
    SourceSnapshotWrite,
    SourceWrite,
    ToolExecutionWrite,
)
from deepscout_core.settings import Settings
from deepscout_providers.defaults import DEFAULT_CHAT_MODELS
from sqlalchemy import select
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
    ResearchPlanRow,
    ResearchQuestionRow,
    ResearchRunRow,
    SearchCandidateRow,
    SourceRow,
    SourceSnapshotRow,
    ToolExecutionRow,
)


class ResearchStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_run(self, payload: ResearchRunCreate, settings: Settings) -> ResearchRunRead:
        budget = payload.budget or settings.default_research_budget()
        provider = settings.llm_provider
        model = settings.llm_model or DEFAULT_CHAT_MODELS[provider]
        row = ResearchRunRow(
            goal=payload.goal,
            status=ResearchRunStatus.PENDING,
            llm_provider=provider.value,
            llm_model=model,
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

    def _snapshot_run_id(self, snapshot_id: uuid.UUID) -> uuid.UUID:
        snapshot = self._session.get(SourceSnapshotRow, snapshot_id)
        if snapshot is None:
            raise LookupError(f"SourceSnapshot {snapshot_id} not found")
        source = self._session.get(SourceRow, snapshot.source_id)
        if source is None:
            raise LookupError(f"Source {snapshot.source_id} not found")
        return source.research_run_id

    def _require_run(self, run_id: uuid.UUID) -> ResearchRunRow:
        row = self._session.get(ResearchRunRow, run_id)
        if row is None:
            raise LookupError(f"ResearchRun {run_id} not found")
        return row


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _run_to_read(row: ResearchRunRow) -> ResearchRunRead:
    return ResearchRunRead(
        id=row.id,
        goal=row.goal,
        status=row.status,
        llm_provider=row.llm_provider,
        llm_model=row.llm_model,
        budget=_budget_from_run(row),
        created_at=row.created_at,
        updated_at=row.updated_at,
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
    return BudgetConsumption(
        iterations=consumption.iterations + int(delta)
        if metric == BudgetMetric.ITERATIONS
        else consumption.iterations,
        wall_time_seconds=consumption.wall_time_seconds + int(delta)
        if metric == BudgetMetric.WALL_TIME
        else consumption.wall_time_seconds,
        total_tokens=consumption.total_tokens + int(delta)
        if metric == BudgetMetric.TOKENS
        else consumption.total_tokens,
        cost_usd=consumption.cost_usd + delta
        if metric == BudgetMetric.COST
        else consumption.cost_usd,
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
