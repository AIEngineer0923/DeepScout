"""Failure taxonomy + HTTP 429 / 5xx classification."""

import httpx
from deepscout_research.errors import ErrorClass, classify_exception, is_fallback_eligible
from deepscout_research.retry import NonRetryableError, RetryPolicy, is_retryable, run_with_retry


def test_classify_429_and_5xx() -> None:
    req = httpx.Request("GET", "https://example.test")
    r429 = httpx.Response(429, request=req)
    r503 = httpx.Response(503, request=req)
    assert classify_exception(httpx.HTTPStatusError("lim", request=req, response=r429)) == (
        ErrorClass.RATE_LIMITED
    )
    assert classify_exception(httpx.HTTPStatusError("bad", request=req, response=r503)) == (
        ErrorClass.TRANSIENT_PROVIDER_ERROR
    )
    assert is_fallback_eligible(ErrorClass.RATE_LIMITED)
    assert is_fallback_eligible(ErrorClass.TIMEOUT)
    assert not is_fallback_eligible(ErrorClass.SECURITY_ERROR)


def test_429_is_retryable_but_bounded() -> None:
    req = httpx.Request("GET", "https://example.test")
    calls = {"n": 0}

    def always_429() -> None:
        calls["n"] += 1
        raise httpx.HTTPStatusError(
            "rate",
            request=req,
            response=httpx.Response(429, request=req),
        )

    try:
        run_with_retry(
            always_429,
            policy=RetryPolicy(max_attempts=3, base_delay_s=0.01, jitter=False),
        )
        raise AssertionError("expected raise")
    except httpx.HTTPStatusError:
        pass
    assert calls["n"] == 3
    assert is_retryable(
        httpx.HTTPStatusError("rate", request=req, response=httpx.Response(429, request=req))
    )


def test_security_failure_not_fallback_eligible() -> None:
    assert classify_exception(NonRetryableError("injection")) == ErrorClass.SECURITY_ERROR
    assert not is_fallback_eligible(ErrorClass.SECURITY_ERROR)
