"""Learning effectiveness analytics — deterministic, no provider spend."""

from __future__ import annotations

from deepscout_evaluation.learning.effectiveness import (
    CohortMetrics,
    LearningDebt,
    LearningHealthState,
    PolicyOutcomeVerdict,
    _compare_verdict,
    _derive_health,
    effectiveness_to_dict,
    run_learning_effectiveness_gate,
)


def test_compare_verdict_improved() -> None:
    before = CohortMetrics(6, 0.6, 10.0, 30.0, 0.2)
    after = CohortMetrics(6, 0.72, 9.0, 28.0, 0.1)
    assert (
        _compare_verdict(before, after, quality_delta=0.12) == PolicyOutcomeVerdict.IMPROVED
    )


def test_compare_verdict_insufficient_data() -> None:
    before = CohortMetrics(2, 0.9, 10.0, 30.0, 0.0)
    after = CohortMetrics(6, 0.5, 10.0, 30.0, 0.5)
    assert (
        _compare_verdict(before, after, quality_delta=-0.4)
        == PolicyOutcomeVerdict.INSUFFICIENT_DATA
    )


def test_derive_health_regression() -> None:
    debt = LearningDebt(0, 0, 0, 0, 0, 0)
    health, _ = _derive_health(
        regressed=1, debt=debt, counts={"terminal_runs": 20}, monitoring_active=0
    )
    assert health == LearningHealthState.REGRESSION_DETECTED


def test_effectiveness_gate_passes() -> None:
    report = run_learning_effectiveness_gate()
    assert report.passed
    assert len(report.cases) >= 10


def test_effectiveness_to_dict_shape() -> None:
    from deepscout_evaluation.learning.effectiveness import LearningEffectivenessReport

    payload = effectiveness_to_dict(
        LearningEffectivenessReport(
            health=LearningHealthState.INSUFFICIENT_DATA,
            health_reason="test",
            production_counts={"terminal_runs": 1},
            policy_win_rate=None,
            rollback_rate=None,
            false_promotion_rate=None,
            mean_time_to_remediation_hours=None,
            debt=LearningDebt(1, 0, 0, 0, 0, 1),
        )
    )
    assert payload["health"] == "insufficient_data"
    assert payload["debt"]["unresolved_cases"] == 1
