"""Semantic evaluation result states — distinct from registry applicability."""

from __future__ import annotations

from enum import StrEnum


class EvaluationResultStatus(StrEnum):
  PASSED = "passed"
  FAILED = "failed"
  SCORE = "score"
  NOT_APPLICABLE = "not_applicable"
  UNAVAILABLE = "unavailable"
  SKIPPED = "skipped"
  ERROR = "error"
  PENDING = "pending"
