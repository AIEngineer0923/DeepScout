"""Tests for multi-policy family bounds and resolution."""

from __future__ import annotations

from deepscout_evaluation.learning.policy_families import (
    PolicyFamily,
    clamp_payload,
    merge_baseline,
    policy_key_for,
)
from deepscout_evaluation.learning.policy_resolver import resolve_effective_runtime_policy


class _StubStore:
    def learning_tables_available(self) -> bool:
        return False


def test_hard_bounds_clamp_gap_bonus() -> None:
    payload = clamp_payload(
        {"gap_queries_per_round_bonus": 99},
        family=PolicyFamily.CORRECTIVE_RESEARCH,
    )
    assert payload["gap_queries_per_round_bonus"] == 1


def test_policy_key_format() -> None:
    assert policy_key_for(PolicyFamily.RETRIEVAL) == "global.retrieval"
    scoped = policy_key_for(PolicyFamily.RETRIEVAL, class_suffix="semantic")
    assert scoped == "global.retrieval.semantic"


def test_resolve_defaults_without_db() -> None:
    from deepscout_core.settings import get_settings

    effective = resolve_effective_runtime_policy(_StubStore(), get_settings())
    assert effective.corrective_research["gap_queries_per_round_bonus"] == 0
    assert effective.retrieval["retrieval_candidate_k_multiplier"] == 1.0


def test_merge_baseline_isolates_families() -> None:
    merged = merge_baseline(PolicyFamily.RETRIEVAL, {"retrieval_candidate_k_multiplier": 1.2})
    assert "gap_queries_per_round_bonus" not in merged
    assert merged["retrieval_candidate_k_multiplier"] == 1.2
