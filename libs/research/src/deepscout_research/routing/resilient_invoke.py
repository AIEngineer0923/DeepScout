"""Bounded invoke with application-owned retry + optional capability-safe fallback."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from deepscout_core.domain.enums import AgentRole
from deepscout_core.settings import Settings
from deepscout_providers.config import application_retry_policy
from deepscout_research.errors import classify_exception, is_fallback_eligible
from deepscout_research.retry import RetryPolicy, run_with_retry
from deepscout_research.routing.capabilities import ModelRequirements
from deepscout_research.routing.model_router import (
    IncompatibleFallbackError,
    ModelRouter,
    ModelSelection,
)
from deepscout_research.routing.provider_health import ProviderHealthRegistry

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class RoutedInvokeResult[T]:
    value: T
    selection: ModelSelection
    attempts: int
    error_class: str | None = None


def invoke_with_resilience[T](
    *,
    settings: Settings,
    role: AgentRole,
    operation: Callable[[ModelSelection], T],
    requirements: ModelRequirements,
    router: ModelRouter | None = None,
    health: ProviderHealthRegistry | None = None,
    retry_policy: RetryPolicy | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> RoutedInvokeResult[T]:
    """Application-owned retry; fallback only when requirements.fallback_allowed.

    Retry ownership: this helper + ``run_with_retry`` are the sole logical retry
    authority. LangChain/provider ``max_retries`` must stay at
    ``PROVIDER_TRANSPORT_MAX_RETRIES`` (0). Embedding callers must never use
    cross-provider fallback.
    """
    active_health = health
    router = router or ModelRouter(settings, health=active_health)
    policy = retry_policy or application_retry_policy(settings)
    attempts = 0
    last_exc: BaseException | None = None

    def _call(selection: ModelSelection) -> T:
        nonlocal attempts
        attempts += 1
        return operation(selection)

    primary = router.resolve(role, requirements=requirements)

    try:

        def primary_op() -> T:
            return _call(primary)

        value = run_with_retry(primary_op, policy=policy, cancelled=cancelled)
        if active_health is not None:
            active_health.record_success(primary.provider)
        return RoutedInvokeResult(value=value, selection=primary, attempts=attempts)
    except Exception as exc:
        last_exc = exc
        error_class = classify_exception(exc)
        if active_health is not None:
            active_health.record_failure(primary.provider, reason=str(exc))
        if not requirements.fallback_allowed or not is_fallback_eligible(error_class):
            raise

    try:
        fallback = router.select_with_fallback(
            role,
            requirements=requirements,
            prefer_fallback=True,
            fallback_reason=(classify_exception(last_exc).value if last_exc else "primary_failed"),
        )
    except IncompatibleFallbackError as fb_err:
        raise last_exc from fb_err

    value = run_with_retry(lambda: _call(fallback), policy=policy, cancelled=cancelled)
    if active_health is not None:
        active_health.record_success(fallback.provider)
    return RoutedInvokeResult(
        value=value,
        selection=fallback,
        attempts=attempts,
        error_class=classify_exception(last_exc).value if last_exc else None,
    )


def max_effective_provider_attempts(
    *,
    llm_max_retries: int,
    fallback_allowed: bool,
) -> int:
    """Upper bound when transport retries are disabled (max_retries=0)."""
    per_model = max(1, int(llm_max_retries))
    return per_model * (2 if fallback_allowed else 1)
