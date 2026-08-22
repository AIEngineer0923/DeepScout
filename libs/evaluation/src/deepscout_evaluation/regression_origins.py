"""Regression fixture origin taxonomy and validation."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class RegressionOrigin(StrEnum):
    DEVELOPMENT_SYNTHETIC = "development_synthetic"
    BENCHMARK_FIXTURE = "benchmark_fixture"
    PRODUCTION_CANDIDATE = "production_candidate"
    PRODUCTION_REVIEWED = "production_reviewed"
    HISTORICAL_REGRESSION = "historical_regression"
    PRODUCTION_UNSANITIZED = "production_unsanitized"


CI_ALLOWED_ORIGINS = frozenset(
    {
        RegressionOrigin.DEVELOPMENT_SYNTHETIC,
        RegressionOrigin.BENCHMARK_FIXTURE,
        RegressionOrigin.PRODUCTION_REVIEWED,
        RegressionOrigin.HISTORICAL_REGRESSION,
    }
)


class OriginMetadata(BaseModel):
    """Per-case origin semantics for documentation and gate policy."""

    origin: RegressionOrigin
    human_reviewed: bool = False
    sanitized: bool = True
    safe_to_commit: bool = True
    contains_synthetic_pattern: bool = False
    derived_from_production: bool = False
    notes: str = ""


def origin_metadata_for(origin: str) -> OriginMetadata:
    try:
        parsed = RegressionOrigin(origin)
    except ValueError:
        return OriginMetadata(
            origin=RegressionOrigin.PRODUCTION_UNSANITIZED,
            human_reviewed=False,
            sanitized=False,
            safe_to_commit=False,
            notes=f"unknown origin: {origin}",
        )
    if parsed == RegressionOrigin.DEVELOPMENT_SYNTHETIC:
        return OriginMetadata(
            origin=parsed,
            contains_synthetic_pattern=True,
            derived_from_production=False,
        )
    if parsed == RegressionOrigin.BENCHMARK_FIXTURE:
        return OriginMetadata(
            origin=parsed,
            contains_synthetic_pattern=True,
            derived_from_production=False,
        )
    if parsed == RegressionOrigin.PRODUCTION_CANDIDATE:
        return OriginMetadata(
            origin=parsed,
            human_reviewed=False,
            safe_to_commit=False,
            derived_from_production=True,
            notes="Must not enter CI baseline until reviewed.",
        )
    if parsed == RegressionOrigin.PRODUCTION_REVIEWED:
        return OriginMetadata(
            origin=parsed,
            human_reviewed=True,
            sanitized=True,
            safe_to_commit=True,
            derived_from_production=True,
        )
    if parsed == RegressionOrigin.HISTORICAL_REGRESSION:
        return OriginMetadata(
            origin=parsed,
            human_reviewed=True,
            sanitized=True,
            safe_to_commit=True,
        )
    return OriginMetadata(
        origin=parsed,
        human_reviewed=False,
        sanitized=False,
        safe_to_commit=False,
    )


def validate_case_origins(cases: list[dict], *, corpus_type: str) -> list[str]:
    errors: list[str] = []
    for case in cases:
        origin = case.get("origin", "")
        case_id = case.get("case_id", "?")
        if corpus_type == "production_reviewed" and origin != RegressionOrigin.PRODUCTION_REVIEWED:
            errors.append(
                f"{case_id}: production_reviewed corpus requires production_reviewed origin"
            )
        if corpus_type == "synthetic_regression" and origin not in {
            RegressionOrigin.DEVELOPMENT_SYNTHETIC,
            RegressionOrigin.HISTORICAL_REGRESSION,
        }:
            errors.append(
                f"{case.get('case_id')}: synthetic corpus requires development_synthetic origin"
            )
        if origin == RegressionOrigin.PRODUCTION_UNSANITIZED:
            errors.append(f"{case_id}: production_unsanitized forbidden")
        if origin == RegressionOrigin.PRODUCTION_CANDIDATE:
            errors.append(f"{case_id}: production_candidate must not be committed in corpus")
    return errors
