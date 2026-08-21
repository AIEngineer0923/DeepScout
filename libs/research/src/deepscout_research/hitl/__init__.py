"""HITL policy, payload binding, and durable review service."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from deepscout_core.domain.enums import (
    ResearchRunStatus,
    ReviewDecisionKind,
    ReviewReasonCode,
    ReviewRequestStatus,
    ReviewRiskLevel,
)
from deepscout_core.settings import Settings
from pydantic import BaseModel, Field, field_validator

from deepscout_research.approval import ApprovalDecision, is_authoritative_approval

POLICY_VERSION = "hitl-v1"
LOCAL_OPERATOR = "local_operator"
AUTHORITATIVE_SOURCES = frozenset({"api", "ui", "operator"})


class PolicyVerdict(StrEnum):
    ALLOW_AUTONOMOUS = "allow_autonomous"
    REQUIRE_REVIEW = "require_review"
    DENY = "deny"


class BudgetExtensionPayload(BaseModel):
    current_max_iterations: int
    current_max_tool_calls: int
    current_max_sources: int
    requested_extra_iterations: int = Field(ge=0, le=20)
    requested_extra_tool_calls: int = Field(ge=0, le=100)
    requested_extra_sources: int = Field(ge=0, le=50)
    consumed_iterations: int
    consumed_tool_calls: int
    consumed_sources: int
    consumed_cost_usd: float | None = None
    cost_status: str = "unknown"

    @field_validator(
        "requested_extra_iterations",
        "requested_extra_tool_calls",
        "requested_extra_sources",
    )
    @classmethod
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("extra budget must be non-negative")
        return value


def canonical_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def payload_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def evaluate_policy(
    reason: ReviewReasonCode,
    settings: Settings,
) -> PolicyVerdict:
    if not settings.hitl_enabled:
        if reason == ReviewReasonCode.SECURITY_SENSITIVE_ACTION:
            return PolicyVerdict.DENY
        return PolicyVerdict.ALLOW_AUTONOMOUS
    if reason == ReviewReasonCode.BUDGET_EXTENSION:
        if settings.hitl_budget_extension_requires_review:
            return PolicyVerdict.REQUIRE_REVIEW
        return PolicyVerdict.ALLOW_AUTONOMOUS
    if reason in {
        ReviewReasonCode.SECURITY_SENSITIVE_ACTION,
        ReviewReasonCode.DESTRUCTIVE_OPERATION,
        ReviewReasonCode.GLOBAL_KNOWLEDGE_PROMOTION,
        ReviewReasonCode.KNOWLEDGE_DELETION,
        ReviewReasonCode.PRIVILEGED_TOOL,
        ReviewReasonCode.EXTERNAL_WRITE,
        ReviewReasonCode.MANUAL_USER_REQUEST,
        ReviewReasonCode.HUMAN_INPUT_REQUIRED,
    }:
        return PolicyVerdict.REQUIRE_REVIEW
    return PolicyVerdict.ALLOW_AUTONOMOUS


@dataclass(frozen=True, slots=True)
class ResolveResult:
    review_id: uuid.UUID
    status: ReviewRequestStatus
    run_status: ResearchRunStatus
    applied: bool


class HumanReviewService:
    """Operational HITL — never accepts model/RAG/Wiki/LangSmith as authority."""

    def __init__(self, store: Any, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    def create_budget_extension_review(
        self,
        run_id: uuid.UUID,
        *,
        extra_iterations: int = 2,
        extra_tool_calls: int = 10,
        extra_sources: int = 5,
    ) -> uuid.UUID:
        if evaluate_policy(ReviewReasonCode.BUDGET_EXTENSION, self._settings) != (
            PolicyVerdict.REQUIRE_REVIEW
        ):
            raise ValueError("budget extension review not required by policy")
        run = self._store.get_run(run_id)
        if run is None:
            raise LookupError(f"run {run_id} not found")
        existing = self._store.get_pending_review(run_id, ReviewReasonCode.BUDGET_EXTENSION)
        if existing is not None:
            return existing.id
        consumption = self._store.get_consumption(run_id)
        cost_status = "unknown"
        if run.usage is not None and run.usage.cost_status is not None:
            cost_status = (
                run.usage.cost_status.value
                if hasattr(run.usage.cost_status, "value")
                else str(run.usage.cost_status)
            )
        payload = BudgetExtensionPayload(
            current_max_iterations=run.budget.max_iterations,
            current_max_tool_calls=run.budget.max_tool_calls,
            current_max_sources=run.budget.max_sources,
            requested_extra_iterations=extra_iterations,
            requested_extra_tool_calls=extra_tool_calls,
            requested_extra_sources=extra_sources,
            consumed_iterations=consumption.iterations,
            consumed_tool_calls=consumption.tool_calls,
            consumed_sources=consumption.sources,
            consumed_cost_usd=run.usage.cost_usd if run.usage is not None else None,
            cost_status=cost_status,
        )
        body = payload.model_dump()
        expires = None
        hours = self._settings.hitl_default_review_expiry_hours
        if hours and hours > 0:
            expires = datetime.now(UTC) + timedelta(hours=int(hours))
        review_id = self._store.create_review_request(
            research_run_id=run_id,
            reason_code=ReviewReasonCode.BUDGET_EXTENSION,
            risk_level=ReviewRiskLevel.HIGH,
            title="Additional research budget required",
            explanation=(
                "The configured research limits have been reached. "
                "Approve an extension to continue, edit the amounts, or stop and synthesize."
            ),
            proposed_action_type="budget_extension",
            proposed_action_payload=body,
            payload_hash=payload_hash(body),
            created_by_component="orchestrator.budget",
            expires_at=expires,
            policy_version=POLICY_VERSION,
        )
        self._store.append_review_event(
            review_id,
            run_id,
            event_type="created",
            actor_source="system",
            actor_identity="orchestrator",
            detail={"reason_code": ReviewReasonCode.BUDGET_EXTENSION.value},
        )
        return review_id

    def resolve_review(
        self,
        *,
        run_id: uuid.UUID,
        review_id: uuid.UUID,
        decision_kind: ReviewDecisionKind,
        source: str,
        identity: str = LOCAL_OPERATOR,
        decision_payload: dict[str, Any] | None = None,
        decision_reason: str | None = None,
        rejection_outcome: str = "STOP_AND_SYNTHESIZE",
    ) -> ResolveResult:
        if source not in AUTHORITATIVE_SOURCES:
            raise PermissionError("review resolution requires authoritative source")
        review = self._store.get_review_request(review_id)
        if review is None or review.research_run_id != run_id:
            raise LookupError("review not found for run")
        if review.status in {
            ReviewRequestStatus.APPROVED,
            ReviewRequestStatus.EDITED,
        } and decision_kind in {ReviewDecisionKind.APPROVE, ReviewDecisionKind.EDIT}:
            return ResolveResult(
                review_id=review_id,
                status=review.status,
                run_status=ResearchRunStatus.PENDING,
                applied=False,
            )
        if review.status != ReviewRequestStatus.PENDING:
            raise ValueError(f"review is {review.status.value}, not pending")
        if review.expires_at is not None and review.expires_at <= datetime.now(UTC):
            self._store.update_review_status(
                review_id,
                ReviewRequestStatus.EXPIRED,
                resolved_by=identity,
                resolved_source=source,
            )
            self._store.append_review_event(
                review_id,
                run_id,
                event_type="expired",
                actor_source=source,
                actor_identity=identity,
            )
            raise ValueError("review expired")

        if decision_kind in {ReviewDecisionKind.APPROVE, ReviewDecisionKind.EDIT}:
            if not is_authoritative_approval(
                decision=ApprovalDecision.APPROVED,
                source=source,
                untrusted_payload=decision_reason,
            ):
                raise PermissionError("approval not authoritative")

        if decision_kind == ReviewDecisionKind.APPROVE:
            if decision_payload is not None:
                if payload_hash(decision_payload) != review.payload_hash:
                    raise ValueError("approval payload does not match proposed action")
            applied_payload = dict(review.proposed_action_payload)
            self._apply_budget(run_id, applied_payload)
            self._store.update_review_status(
                review_id,
                ReviewRequestStatus.APPROVED,
                resolved_by=identity,
                resolved_source=source,
                decision_kind=ReviewDecisionKind.APPROVE,
                decision_payload=applied_payload,
                decision_reason=decision_reason,
            )
            self._store.append_review_event(
                review_id,
                run_id,
                event_type="approved",
                actor_source=source,
                actor_identity=identity,
                detail={"payload_hash": review.payload_hash},
            )
            self._store.update_run_status(run_id, ResearchRunStatus.PENDING)
            self._store.set_termination_reason(run_id, None)
            return ResolveResult(
                review_id=review_id,
                status=ReviewRequestStatus.APPROVED,
                run_status=ResearchRunStatus.PENDING,
                applied=True,
            )

        if decision_kind == ReviewDecisionKind.EDIT:
            if decision_payload is None:
                raise ValueError("edit requires decision_payload")
            edited = BudgetExtensionPayload.model_validate(
                {
                    **review.proposed_action_payload,
                    "requested_extra_iterations": decision_payload.get(
                        "requested_extra_iterations",
                        review.proposed_action_payload["requested_extra_iterations"],
                    ),
                    "requested_extra_tool_calls": decision_payload.get(
                        "requested_extra_tool_calls",
                        review.proposed_action_payload["requested_extra_tool_calls"],
                    ),
                    "requested_extra_sources": decision_payload.get(
                        "requested_extra_sources",
                        review.proposed_action_payload["requested_extra_sources"],
                    ),
                }
            )
            body = edited.model_dump()
            self._apply_budget(run_id, body)
            self._store.update_review_status(
                review_id,
                ReviewRequestStatus.EDITED,
                resolved_by=identity,
                resolved_source=source,
                decision_kind=ReviewDecisionKind.EDIT,
                decision_payload=body,
                decision_reason=decision_reason,
            )
            self._store.append_review_event(
                review_id,
                run_id,
                event_type="edited",
                actor_source=source,
                actor_identity=identity,
                detail={"payload_hash": payload_hash(body)},
            )
            self._store.update_run_status(run_id, ResearchRunStatus.PENDING)
            self._store.set_termination_reason(run_id, None)
            return ResolveResult(
                review_id=review_id,
                status=ReviewRequestStatus.EDITED,
                run_status=ResearchRunStatus.PENDING,
                applied=True,
            )

        if decision_kind == ReviewDecisionKind.REJECT:
            outcome = rejection_outcome if rejection_outcome in {
                "STOP_AND_SYNTHESIZE",
                "CANCEL_RUN",
            } else "STOP_AND_SYNTHESIZE"
            self._store.update_review_status(
                review_id,
                ReviewRequestStatus.REJECTED,
                resolved_by=identity,
                resolved_source=source,
                decision_kind=ReviewDecisionKind.REJECT,
                decision_reason=decision_reason,
                rejection_outcome=outcome,
            )
            self._store.append_review_event(
                review_id,
                run_id,
                event_type="rejected",
                actor_source=source,
                actor_identity=identity,
                detail={"outcome": outcome},
            )
            if outcome == "CANCEL_RUN":
                self._store.cancel_run(run_id)
                return ResolveResult(
                    review_id=review_id,
                    status=ReviewRequestStatus.REJECTED,
                    run_status=ResearchRunStatus.CANCELLED,
                    applied=True,
                )
            self._store.set_termination_reason(run_id, "budget_exhausted")
            self._store.update_run_status(run_id, ResearchRunStatus.BUDGET_EXHAUSTED)
            return ResolveResult(
                review_id=review_id,
                status=ReviewRequestStatus.REJECTED,
                run_status=ResearchRunStatus.BUDGET_EXHAUSTED,
                applied=True,
            )

        if decision_kind == ReviewDecisionKind.RESPOND:
            if review.reason_code != ReviewReasonCode.HUMAN_INPUT_REQUIRED:
                raise ValueError("respond only valid for human_input_required")
            if not decision_payload or "response" not in decision_payload:
                raise ValueError("respond requires response text")
            self._store.update_review_status(
                review_id,
                ReviewRequestStatus.RESPONDED,
                resolved_by=identity,
                resolved_source=source,
                decision_kind=ReviewDecisionKind.RESPOND,
                decision_payload=decision_payload,
                decision_reason=decision_reason,
            )
            self._store.append_review_event(
                review_id,
                run_id,
                event_type="responded",
                actor_source=source,
                actor_identity=identity,
            )
            self._store.update_run_status(run_id, ResearchRunStatus.PENDING)
            return ResolveResult(
                review_id=review_id,
                status=ReviewRequestStatus.RESPONDED,
                run_status=ResearchRunStatus.PENDING,
                applied=True,
            )

        raise ValueError(f"unsupported decision {decision_kind}")

    def _apply_budget(self, run_id: uuid.UUID, payload: dict[str, Any]) -> None:
        self._store.extend_run_budget(
            run_id,
            extra_iterations=int(payload["requested_extra_iterations"]),
            extra_tool_calls=int(payload["requested_extra_tool_calls"]),
            extra_sources=int(payload["requested_extra_sources"]),
        )
