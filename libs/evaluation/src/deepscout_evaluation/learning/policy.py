"""Versioned learning policies — multi-family, rollback-capable, tenant-scoped."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from deepscout_evaluation.learning.models import PolicyVersion, PromotionDecision, PromotionVerdict
from deepscout_evaluation.learning.policy_families import (
    FAMILY_BASELINES,
    LEGACY_POLICY_KEY,
    PolicyFamily,
    PolicyRiskLevel,
    clamp_payload,
    family_for_payload_delta,
    merge_baseline,
    policy_key_for,
)

# Backward-compatible merged baseline for legacy callers.
DEFAULT_BASELINE_POLICY: dict[str, Any] = {
    **FAMILY_BASELINES[PolicyFamily.CORRECTIVE_RESEARCH],
    **FAMILY_BASELINES[PolicyFamily.RETRIEVAL],
    **FAMILY_BASELINES[PolicyFamily.COST_LATENCY],
}


def apply_promotion(
    decision: PromotionDecision,
    candidate_policy_delta: dict[str, Any],
    *,
    owner_principal_id: UUID | None = None,
    promoted_from_candidate_id: str | None = None,
    policy_family: PolicyFamily | None = None,
    scope_key: str = "global",
) -> PolicyVersion | None:
    if decision.verdict != PromotionVerdict.SAFE_TO_PROMOTE:
        return None
    family = policy_family or family_for_payload_delta(candidate_policy_delta)
    if family is None:
        family = PolicyFamily.CORRECTIVE_RESEARCH
    payload = merge_baseline(family, candidate_policy_delta)
    policy_key = (
        LEGACY_POLICY_KEY
        if family == PolicyFamily.CORRECTIVE_RESEARCH and scope_key == "global"
        else policy_key_for(family, scope=scope_key)
    )
    return PolicyVersion(
        policy_key=policy_key,
        version_label=decision.policy_version_label or f"learning-{family.value}-v1",
        payload=payload,
        active=True,
        promoted_from_candidate_id=promoted_from_candidate_id,
        promotion_reason="; ".join(decision.reasons),
        evidence={"outcome": decision.outcome.value, "policy_family": family.value},
        owner_principal_id=owner_principal_id,
        policy_family=family.value,
        scope_key=scope_key,
    )


def rollback_policy(active: PolicyVersion) -> PolicyVersion:
    family = (
        PolicyFamily(active.policy_family)
        if active.policy_family
        else PolicyFamily.CORRECTIVE_RESEARCH
    )
    return PolicyVersion(
        policy_key=active.policy_key,
        version_label=f"{active.version_label}-rollback",
        payload=merge_baseline(family),
        active=True,
        promotion_reason=f"rollback from {active.version_label}",
        evidence={"rolled_back_from": active.version_label},
        owner_principal_id=active.owner_principal_id,
        policy_family=family.value,
        scope_key=active.scope_key or "global",
    )


def gap_queries_per_round_bonus(policy: dict[str, Any] | None) -> int:
    if not policy:
        return 0
    clamped = clamp_payload(
        {"gap_queries_per_round_bonus": policy.get("gap_queries_per_round_bonus", 0)},
        family=PolicyFamily.CORRECTIVE_RESEARCH,
    )
    return int(clamped.get("gap_queries_per_round_bonus", 0))


def retrieval_candidate_k_multiplier(policy: dict[str, Any] | None) -> float:
    if not policy:
        return 1.0
    clamped = clamp_payload(
        {"retrieval_candidate_k_multiplier": policy.get("retrieval_candidate_k_multiplier", 1.0)},
        family=PolicyFamily.RETRIEVAL,
    )
    return float(clamped.get("retrieval_candidate_k_multiplier", 1.0))


def retrieval_top_k_delta(policy: dict[str, Any] | None) -> int:
    if not policy:
        return 0
    clamped = clamp_payload(
        {"retrieval_top_k_delta": policy.get("retrieval_top_k_delta", 0)},
        family=PolicyFamily.RETRIEVAL,
    )
    return int(clamped.get("retrieval_top_k_delta", 0))


def report_rewrite_bonus(policy: dict[str, Any] | None) -> int:
    if not policy:
        return 0
    clamped = clamp_payload(
        {"report_rewrite_bonus": policy.get("report_rewrite_bonus", 0)},
        family=PolicyFamily.SYNTHESIS,
    )
    return int(clamped.get("report_rewrite_bonus", 0))


def allocation_parallel_preference(policy: dict[str, Any] | None) -> float:
    if not policy:
        return 0.5
    clamped = clamp_payload(
        {"allocation_parallel_preference": policy.get("allocation_parallel_preference", 0.5)},
        family=PolicyFamily.ALLOCATION,
    )
    return float(clamped.get("allocation_parallel_preference", 0.5))


def prefer_lower_cost_strategy(policy: dict[str, Any] | None) -> bool:
    if not policy:
        return False
    return bool(policy.get("prefer_lower_cost_strategy", False))


def search_variant_count_delta(policy: dict[str, Any] | None) -> int:
    if not policy:
        return 0
    clamped = clamp_payload(
        {"search_variant_count_delta": policy.get("search_variant_count_delta", 0)},
        family=PolicyFamily.QUERY_STRATEGY,
    )
    return int(clamped.get("search_variant_count_delta", 0))


def authority_namespace_diversification(policy: dict[str, Any] | None) -> float:
    if not policy:
        return 0.0
    raw = float(policy.get("authority_namespace_diversification", 0.0))
    return float(min(1.0, max(0.0, raw)))


def zero_yield_reformulation_bonus(policy: dict[str, Any] | None) -> int:
    if not policy:
        return 0
    clamped = clamp_payload(
        {"zero_yield_reformulation_bonus": policy.get("zero_yield_reformulation_bonus", 0)},
        family=PolicyFamily.QUERY_STRATEGY,
    )
    return int(clamped.get("zero_yield_reformulation_bonus", 0))


def max_tasks_bonus(policy: dict[str, Any] | None) -> int:
    if not policy:
        return 0
    clamped = clamp_payload(
        {"max_tasks_bonus": policy.get("max_tasks_bonus", 0)},
        family=PolicyFamily.PLANNER,
    )
    return int(clamped.get("max_tasks_bonus", 0))


def planner_decomposition_strictness(policy: dict[str, Any] | None) -> float:
    if not policy:
        return 0.5
    clamped = clamp_payload(
        {"planner_decomposition_strictness": policy.get("planner_decomposition_strictness", 0.5)},
        family=PolicyFamily.PLANNER,
    )
    return float(clamped.get("planner_decomposition_strictness", 0.5))


def low_marginal_yield_threshold_delta(policy: dict[str, Any] | None) -> float:
    if not policy:
        return 0.0
    clamped = clamp_payload(
        {
            "low_marginal_yield_threshold_delta": policy.get(
                "low_marginal_yield_threshold_delta", 0.0
            )
        },
        family=PolicyFamily.SUFFICIENCY,
    )
    return float(clamped.get("low_marginal_yield_threshold_delta", 0.0))


def evidence_sufficiency_threshold_delta(policy: dict[str, Any] | None) -> float:
    if not policy:
        return 0.0
    clamped = clamp_payload(
        {
            "evidence_sufficiency_threshold_delta": policy.get(
                "evidence_sufficiency_threshold_delta", 0.0
            )
        },
        family=PolicyFamily.SUFFICIENCY,
    )
    return float(clamped.get("evidence_sufficiency_threshold_delta", 0.0))


_REASONING_LEVEL_MAP = ("minimal", "low", "medium", "high")


def reasoning_effort_from_policy(policy: dict[str, Any] | None) -> str | None:
    """Map bounded integer level 0-2 to provider effort string, or None for default."""
    if not policy:
        return None
    clamped = clamp_payload(
        {"reasoning_effort_level": policy.get("reasoning_effort_level", 0)},
        family=PolicyFamily.REASONING,
    )
    level = int(clamped.get("reasoning_effort_level", 0))
    if level <= 0:
        return None
    index = min(level, len(_REASONING_LEVEL_MAP) - 1)
    return _REASONING_LEVEL_MAP[index]


def cost_quality_tradeoff(policy: dict[str, Any] | None) -> float:
    if not policy:
        return 0.0
    clamped = clamp_payload(
        {"cost_quality_tradeoff": policy.get("cost_quality_tradeoff", 0.0)},
        family=PolicyFamily.COST_LATENCY,
    )
    return float(clamped.get("cost_quality_tradeoff", 0.0))


def risk_for_family(family: PolicyFamily) -> PolicyRiskLevel:
    from deepscout_evaluation.learning.policy_families import FAMILY_RISK

    return FAMILY_RISK[family]
