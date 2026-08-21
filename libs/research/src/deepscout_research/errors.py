"""Stable application error taxonomy — provider exceptions stay diagnostic context."""

from __future__ import annotations

from enum import StrEnum

import httpx
from deepscout_core.domain.budget import BudgetExhaustedError

from deepscout_research.exceptions import RunCancelledError
from deepscout_research.retry import NonRetryableError


class ErrorClass(StrEnum):
    TRANSIENT_PROVIDER_ERROR = "transient_provider_error"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    INVALID_PROVIDER_RESPONSE = "invalid_provider_response"
    SCHEMA_VALIDATION_ERROR = "schema_validation_error"
    POLICY_ERROR = "policy_error"
    BUDGET_EXCEEDED = "budget_exceeded"
    CANCELLED = "cancelled"
    DEPENDENCY_UNAVAILABLE = "dependency_unavailable"
    DATABASE_ERROR = "database_error"
    SECURITY_ERROR = "security_error"
    PERMANENT_CONFIGURATION_ERROR = "permanent_configuration_error"
    UNKNOWN = "unknown"


def classify_exception(exc: BaseException) -> ErrorClass:
    if isinstance(exc, RunCancelledError):
        return ErrorClass.CANCELLED
    if isinstance(exc, BudgetExhaustedError):
        return ErrorClass.BUDGET_EXCEEDED
    if isinstance(exc, NonRetryableError):
        return ErrorClass.SECURITY_ERROR
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        if status == 429:
            return ErrorClass.RATE_LIMITED
        if status >= 500:
            return ErrorClass.TRANSIENT_PROVIDER_ERROR
        if status in {400, 401, 403, 404, 422}:
            return ErrorClass.INVALID_PROVIDER_RESPONSE
    if isinstance(exc, httpx.TimeoutException | TimeoutError):
        return ErrorClass.TIMEOUT
    if isinstance(exc, httpx.NetworkError | httpx.ConnectError | ConnectionError):
        return ErrorClass.DEPENDENCY_UNAVAILABLE
    if isinstance(exc, ValueError) and "embedding" in str(exc).lower():
        return ErrorClass.PERMANENT_CONFIGURATION_ERROR
    if isinstance(exc, ValueError):
        return ErrorClass.SCHEMA_VALIDATION_ERROR
    return ErrorClass.UNKNOWN


def is_fallback_eligible(error_class: ErrorClass) -> bool:
    return error_class in {
        ErrorClass.TRANSIENT_PROVIDER_ERROR,
        ErrorClass.RATE_LIMITED,
        ErrorClass.TIMEOUT,
        ErrorClass.DEPENDENCY_UNAVAILABLE,
    }


def is_permanent(error_class: ErrorClass) -> bool:
    return error_class in {
        ErrorClass.SECURITY_ERROR,
        ErrorClass.POLICY_ERROR,
        ErrorClass.PERMANENT_CONFIGURATION_ERROR,
        ErrorClass.BUDGET_EXCEEDED,
        ErrorClass.CANCELLED,
    }
