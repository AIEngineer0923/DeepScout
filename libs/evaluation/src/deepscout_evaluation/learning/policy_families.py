"""Typed adaptive policy families with hard bounds and risk classification."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class PolicyFamily(StrEnum):
    CORRECTIVE_RESEARCH = "corrective_research"
    RETRIEVAL = "retrieval"
    QUERY_STRATEGY = "query_strategy"
    PLANNER = "planner"
    ALLOCATION = "allocation"
    SUFFICIENCY = "sufficiency"
    SYNTHESIS = "synthesis"
    REASONING = "reasoning"
    COST_LATENCY = "cost_latency"


class PolicyRiskLevel(StrEnum):
    LOW_RISK_AUTO_ELIGIBLE = "low_risk_auto_eligible"
    MEDIUM_RISK_HITL = "medium_risk_hitl"
    HIGH_RISK_HUMAN_ONLY = "high_risk_human_only"


class PolicyScope(StrEnum):
    GLOBAL = "global"
    TENANT = "tenant"


# Application-owned hard bounds — learning cannot exceed these envelopes.
HARD_BOUNDS: dict[str, tuple[float, float] | tuple[int, int]] = {
    "gap_queries_per_round_bonus": (0, 1),
    "max_corrective_round_bonus": (0, 1),
    "retrieval_top_k_delta": (-3, 3),
    "retrieval_candidate_k_multiplier": (0.8, 1.25),
    "search_variant_count_delta": (-1, 2),
    "zero_yield_reformulation_bonus": (0, 1),
    "planner_decomposition_strictness": (0.0, 1.0),
    "max_tasks_bonus": (0, 2),
    "allocation_parallel_preference": (0.0, 1.0),
    "low_marginal_yield_threshold_delta": (-0.1, 0.1),
    "evidence_sufficiency_threshold_delta": (-0.1, 0.1),
    "report_rewrite_bonus": (0, 1),
    "reasoning_effort_level": (0, 2),
    "prefer_lower_cost_strategy": (0, 1),
    "cost_quality_tradeoff": (-0.2, 0.2),
}

FAMILY_RISK: dict[PolicyFamily, PolicyRiskLevel] = {
    PolicyFamily.CORRECTIVE_RESEARCH: PolicyRiskLevel.LOW_RISK_AUTO_ELIGIBLE,
    PolicyFamily.RETRIEVAL: PolicyRiskLevel.LOW_RISK_AUTO_ELIGIBLE,
    PolicyFamily.QUERY_STRATEGY: PolicyRiskLevel.LOW_RISK_AUTO_ELIGIBLE,
    PolicyFamily.PLANNER: PolicyRiskLevel.MEDIUM_RISK_HITL,
    PolicyFamily.ALLOCATION: PolicyRiskLevel.MEDIUM_RISK_HITL,
    PolicyFamily.SUFFICIENCY: PolicyRiskLevel.LOW_RISK_AUTO_ELIGIBLE,
    PolicyFamily.SYNTHESIS: PolicyRiskLevel.MEDIUM_RISK_HITL,
    PolicyFamily.REASONING: PolicyRiskLevel.MEDIUM_RISK_HITL,
    PolicyFamily.COST_LATENCY: PolicyRiskLevel.LOW_RISK_AUTO_ELIGIBLE,
}

FAMILY_BASELINES: dict[PolicyFamily, dict[str, Any]] = {
    PolicyFamily.CORRECTIVE_RESEARCH: {
        "gap_queries_per_round_bonus": 0,
        "max_corrective_round_bonus": 0,
    },
    PolicyFamily.RETRIEVAL: {
        "retrieval_top_k_delta": 0,
        "retrieval_candidate_k_multiplier": 1.0,
        "deterministic_rerank_weight": 1.0,
    },
    PolicyFamily.QUERY_STRATEGY: {
        "search_variant_count_delta": 0,
        "authority_namespace_diversification": 0.0,
        "zero_yield_reformulation_bonus": 0,
    },
    PolicyFamily.PLANNER: {
        "planner_decomposition_strictness": 0.5,
        "max_tasks_bonus": 0,
        "dependency_validator_strict": True,
    },
    PolicyFamily.ALLOCATION: {
        "allocation_parallel_preference": 0.5,
        "duplicate_work_avoidance": True,
    },
    PolicyFamily.SUFFICIENCY: {
        "low_marginal_yield_threshold_delta": 0.0,
        "evidence_sufficiency_threshold_delta": 0.0,
    },
    PolicyFamily.SYNTHESIS: {
        "report_rewrite_bonus": 0,
        "synthesis_prompt_version": "default",
    },
    PolicyFamily.REASONING: {
        "reasoning_effort_level": 0,
    },
    PolicyFamily.COST_LATENCY: {
        "prefer_lower_cost_strategy": False,
        "cost_quality_tradeoff": 0.0,
    },
}

# Keys owned by each family — used to route policy_delta on promotion.
FAMILY_PAYLOAD_KEYS: dict[PolicyFamily, frozenset[str]] = {
    family: frozenset(baseline.keys()) for family, baseline in FAMILY_BASELINES.items()
}

# Legacy single-key compatibility
LEGACY_POLICY_KEY = "global.corrective_research"


def policy_key_for(
    family: PolicyFamily, *, scope: str = "global", class_suffix: str | None = None
) -> str:
    if class_suffix:
        return f"{scope}.{family.value}.{class_suffix}"
    return f"{scope}.{family.value}"


def family_for_policy_key(policy_key: str) -> PolicyFamily | None:
    parts = policy_key.split(".")
    if len(parts) < 2:
        return None
    family_part = parts[1] if parts[0] in ("global", "tenant") else parts[0]
    if policy_key == LEGACY_POLICY_KEY:
        return PolicyFamily.CORRECTIVE_RESEARCH
    try:
        return PolicyFamily(family_part)
    except ValueError:
        return None


def family_for_payload_delta(delta: dict[str, Any]) -> PolicyFamily | None:
    keys = set(delta.keys())
    if not keys:
        return None
    for family, owned in FAMILY_PAYLOAD_KEYS.items():
        if keys & owned:
            return family
    return None


def clamp_value(key: str, value: Any) -> Any:
    if key not in HARD_BOUNDS:
        return value
    lo, hi = HARD_BOUNDS[key]
    if isinstance(value, bool):
        return value
    if isinstance(value, int) or (isinstance(value, float) and key.endswith("_bonus")):
        return int(min(hi, max(lo, int(value))))
    if isinstance(value, (int, float)):
        return float(min(hi, max(lo, float(value))))
    return value


def clamp_payload(payload: dict[str, Any], *, family: PolicyFamily | None = None) -> dict[str, Any]:
    allowed = FAMILY_PAYLOAD_KEYS.get(family) if family else None
    out: dict[str, Any] = {}
    for key, value in payload.items():
        if allowed is not None and key not in allowed:
            continue
        if key == "dependency_validator_strict" or key == "duplicate_work_avoidance":
            out[key] = bool(value)
        elif key == "prefer_lower_cost_strategy":
            out[key] = bool(value)
        elif key == "synthesis_prompt_version":
            out[key] = str(value)[:32]
        else:
            out[key] = clamp_value(key, value)
    return out


def merge_baseline(family: PolicyFamily, delta: dict[str, Any] | None = None) -> dict[str, Any]:
    base = dict(FAMILY_BASELINES[family])
    if delta:
        base.update(clamp_payload(delta, family=family))
    return base


def all_families_baseline() -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for family in PolicyFamily:
        merged.update(FAMILY_BASELINES[family])
    return merged


class EffectivePolicyVersionRef(BaseModel):
    policy_family: str
    policy_key: str
    version_label: str
    version_id: str | None = None


class EffectiveRuntimePolicy(BaseModel):
    """Resolved policy for a run — inspectable and snapshot-friendly."""

    versions: list[EffectivePolicyVersionRef] = Field(default_factory=list)
    corrective_research: dict[str, Any] = Field(default_factory=dict)
    retrieval: dict[str, Any] = Field(default_factory=dict)
    query_strategy: dict[str, Any] = Field(default_factory=dict)
    planner: dict[str, Any] = Field(default_factory=dict)
    allocation: dict[str, Any] = Field(default_factory=dict)
    sufficiency: dict[str, Any] = Field(default_factory=dict)
    synthesis: dict[str, Any] = Field(default_factory=dict)
    reasoning: dict[str, Any] = Field(default_factory=dict)
    cost_latency: dict[str, Any] = Field(default_factory=dict)

    def family_payload(self, family: PolicyFamily) -> dict[str, Any]:
        return getattr(self, family.value)

    def to_snapshot(self) -> dict[str, Any]:
        return {
            "learning_policy_versions": [v.model_dump() for v in self.versions],
            "effective": {family.value: self.family_payload(family) for family in PolicyFamily},
        }
