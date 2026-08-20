from deepscout_research.graphs.correction import run_correction_loop


def test_passing_artifact_skips_critic() -> None:
    result = run_correction_loop(artifact_type="report", passed=True, issues=[])
    assert result["status"] == "passed"
    assert result.get("critic_invoked") is False


def test_failing_artifact_invokes_critic_once() -> None:
    result = run_correction_loop(
        artifact_type="report",
        passed=False,
        issues=["unsupported claim in section 2"],
        max_rounds=1,
    )
    assert result.get("critic_invoked") is True
    assert result["status"] == "failed"
    assert "unsupported claim" in result["issues"][0]
