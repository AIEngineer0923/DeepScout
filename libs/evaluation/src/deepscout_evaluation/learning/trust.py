"""Trust levels and poisoning defenses for learning data."""

from __future__ import annotations

from deepscout_evaluation.learning.models import TrustLevel
from deepscout_evaluation.regression_origins import RegressionOrigin
from deepscout_evaluation.retrieval_sanitizer import (
    contains_secret_material,
    sanitize_learning_export,
    validate_safe_for_export,
)

_PROMOTION_TRUST_FLOOR = {
    RegressionOrigin.DEVELOPMENT_SYNTHETIC: TrustLevel.VALIDATED_LEARNING,
    RegressionOrigin.BENCHMARK_FIXTURE: TrustLevel.VALIDATED_LEARNING,
    RegressionOrigin.HISTORICAL_REGRESSION: TrustLevel.REVIEWED_CASE,
    RegressionOrigin.PRODUCTION_REVIEWED: TrustLevel.REVIEWED_CASE,
    RegressionOrigin.PRODUCTION_CANDIDATE: TrustLevel.SANITIZED_CANDIDATE,
    RegressionOrigin.PRODUCTION_UNSANITIZED: TrustLevel.UNTRUSTED_OBSERVATION,
}

_TRUST_RANK = {
    TrustLevel.UNTRUSTED_OBSERVATION: 0,
    TrustLevel.SANITIZED_CANDIDATE: 1,
    TrustLevel.REVIEWED_CASE: 2,
    TrustLevel.VALIDATED_LEARNING: 3,
    TrustLevel.PROMOTED_POLICY: 4,
}


def trust_for_origin(origin: str | RegressionOrigin) -> TrustLevel:
    try:
        parsed = origin if isinstance(origin, RegressionOrigin) else RegressionOrigin(origin)
    except ValueError:
        return TrustLevel.UNTRUSTED_OBSERVATION
    return _PROMOTION_TRUST_FLOOR.get(parsed, TrustLevel.UNTRUSTED_OBSERVATION)


def trust_meets_minimum(actual: TrustLevel, required: TrustLevel) -> bool:
    return _TRUST_RANK[actual] >= _TRUST_RANK[required]


def validate_learning_payload(payload: dict, *, required_trust: TrustLevel) -> list[str]:
    errors = validate_safe_for_export(payload)
    if errors:
        return errors
    origin = payload.get("origin", RegressionOrigin.PRODUCTION_UNSANITIZED.value)
    actual = trust_for_origin(str(origin))
    if not trust_meets_minimum(actual, required_trust):
        errors.append(
            f"trust_level {actual.value} below required {required_trust.value} for origin {origin}"
        )
    text_blob = " ".join(str(value) for value in payload.values())
    if contains_secret_material(text_blob):
        errors.append("secret material detected in learning payload")
    return errors


def sanitize_observation_payload(payload: dict) -> tuple[dict, list[str]]:
    sanitized, errors = sanitize_learning_export(payload)
    if errors:
        return sanitized, errors
    sanitized["sanitized"] = True
    sanitized["trust_level"] = TrustLevel.SANITIZED_CANDIDATE.value
    return sanitized, []
