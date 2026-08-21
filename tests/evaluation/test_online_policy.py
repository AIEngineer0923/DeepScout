from deepscout_evaluation.online_policy import ONLINE_EVAL_POLICY


def test_online_policy_keeps_llm_judges_at_zero_sample() -> None:
    cheap = next(
        rule for rule in ONLINE_EVAL_POLICY if rule.evaluator_id == "deepscout-claim-has-evidence"
    )
    judges = [rule for rule in ONLINE_EVAL_POLICY if rule.evaluator_id.startswith("llm_judge")]
    assert cheap.sampling_rate == 1.0
    assert cheap.attached is True
    assert judges
    assert all(rule.sampling_rate == 0.0 for rule in judges)
