#!/usr/bin/env python3
"""Fast deterministic validation for the research-completeness regression manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from deepscout_core.domain.research_profiles import research_profile
from deepscout_evaluation.regression_origins import validate_case_origins
from deepscout_evaluation.retrieval_sanitizer import validate_fixture_privacy

FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "libs/evaluation/data/research_completeness_regressions_v1.json"
)
REQUIRED_CASES = {
    "formal-report-material-gap",
    "qualitative-only-quantitative-request",
    "one-sided-requested-comparison",
    "secondary-only-primary-expected",
    "searched-zero-results",
    "budget-exhausted-gap",
    "duplicate-localized-bibliography",
    "mode-depth-ordering",
    "terminal-failure-learning-observation",
}


def main() -> int:
    fixture = json.loads(FIXTURE.read_text())
    errors = validate_fixture_privacy(fixture)
    errors.extend(
        validate_case_origins(
            fixture.get("cases", []),
            corpus_type=str(fixture.get("corpus_type", "")),
        )
    )
    ids = {str(case.get("case_id")) for case in fixture.get("cases", [])}
    missing = REQUIRED_CASES - ids
    if missing:
        errors.append(f"missing regression cases: {', '.join(sorted(missing))}")
    quick = research_profile("quick")
    standard = research_profile("standard")
    deep = research_profile("deep")
    if not (
        quick.max_requirement_tasks
        < standard.max_requirement_tasks
        < deep.max_requirement_tasks
    ):
        errors.append("mode task depth is not strictly ordered")
    if not (
        quick.max_coverage_rounds
        < standard.max_coverage_rounds
        < deep.max_coverage_rounds
    ):
        errors.append("mode corrective depth is not strictly ordered")
    if errors:
        for error in errors:
            print(f"FAIL: {error}")
        return 1
    print(f"PASS: {len(ids)} sanitized completeness regressions validated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
