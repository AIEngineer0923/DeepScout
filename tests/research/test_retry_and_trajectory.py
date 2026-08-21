from deepscout_evaluation.trajectory import TrajectoryMatchMode, match_trajectory
from deepscout_research.retry import NonRetryableError, is_retryable, run_with_retry


def test_retry_succeeds_after_transient_failure() -> None:
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise ConnectionError("reset")
        return "ok"

    assert run_with_retry(flaky) == "ok"
    assert calls["n"] == 3


def test_security_rejection_is_not_retryable() -> None:
    assert is_retryable(NonRetryableError("ssrf")) is False
    try:
        run_with_retry(lambda: (_ for _ in ()).throw(NonRetryableError("ssrf")))
        raise AssertionError("should have raised")
    except NonRetryableError:
        pass


def test_parallel_trajectory_unordered_and_superset() -> None:
    required = ["worker:a", "worker:b", "phase.report"]
    actual_ab = ["phase.plan", "worker:a", "worker:b", "phase.report"]
    actual_ba = ["phase.plan", "worker:b", "worker:a", "phase.report"]
    assert match_trajectory(actual_ab, required, mode=TrajectoryMatchMode.SUPERSET)
    assert match_trajectory(actual_ba, required, mode=TrajectoryMatchMode.SUPERSET)
    assert match_trajectory(
        ["worker:b", "worker:a"],
        ["worker:a", "worker:b"],
        mode=TrajectoryMatchMode.UNORDERED,
    )
    assert match_trajectory(
        ["worker:a", "worker:b"],
        ["worker:a", "worker:b"],
        mode=TrajectoryMatchMode.EXACT,
    )
    assert not match_trajectory(
        ["worker:a", "worker:b"],
        ["worker:b", "worker:a"],
        mode=TrajectoryMatchMode.EXACT,
    )
