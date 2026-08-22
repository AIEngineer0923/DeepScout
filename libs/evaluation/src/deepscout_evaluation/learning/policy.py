"""Versioned learning policies — rollback-capable, tenant-scoped."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from deepscout_evaluation.learning.models import PolicyVersion, PromotionDecision, PromotionVerdict

DEFAULT_BASELINE_POLICY: dict[str, Any] = {
    "gap_queries_per_round_bonus": 0,
    "retrieval_candidate_k_multiplier": 1.0,
    "prefer_lower_cost_strategy": False,
}

_GLOBAL_POLICY_KEY = "global.corrective_research"


def apply_promotion(
    decision: PromotionDecision,
    candidate_policy_delta: dict[str, Any],
    *,
    owner_principal_id: UUID | None = None,
    promoted_from_candidate_id: str | None = None,
) -> PolicyVersion | None:
    if decision.verdict != PromotionVerdict.SAFE_TO_PROMOTE:
        return None
    payload = {**DEFAULT_BASELINE_POLICY, **candidate_policy_delta}
    return PolicyVersion(
        policy_key=_GLOBAL_POLICY_KEY,
        version_label=decision.policy_version_label or "learning-policy-v1",
        payload=payload,
        active=True,
        promoted_from_candidate_id=promoted_from_candidate_id,
        promotion_reason="; ".join(decision.reasons),
        evidence={"outcome": decision.outcome.value},
        owner_principal_id=owner_principal_id,
    )


def rollback_policy(active: PolicyVersion) -> PolicyVersion:
    return PolicyVersion(
        policy_key=active.policy_key,
        version_label=f"{active.version_label}-rollback",
        payload=dict(DEFAULT_BASELINE_POLICY),
        active=True,
        promotion_reason=f"rollback from {active.version_label}",
        evidence={"rolled_back_from": active.version_label},
        owner_principal_id=active.owner_principal_id,
    )


def gap_queries_per_round_bonus(policy: dict[str, Any] | None) -> int:
    if not policy:
        return 0
    return min(1, max(0, int(policy.get("gap_queries_per_round_bonus", 0))))
