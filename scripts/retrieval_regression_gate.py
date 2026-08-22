#!/usr/bin/env python3
"""Deterministic retrieval regression gate — CI-safe, no provider spend."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from deepscout_core.settings import get_settings
from deepscout_evaluation.retrieval_regression import (
    format_regression_report,
    load_production_regressions,
    load_regression_baseline,
    report_to_dict,
    run_deterministic_gate,
    validate_regression_fixture,
)
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepScout retrieval regression gate")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="Production regression fixture JSON",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=None,
        help="Regression baseline JSON",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate fixture schema/privacy only",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human report",
    )
    args = parser.parse_args()

    fixture = load_production_regressions(args.fixture)
    errors = validate_regression_fixture(fixture)
    if errors:
        print("Fixture validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    if args.validate_only:
        print("Fixture validation passed.")
        return 0

    settings = get_settings()
    session_factory = get_session_factory(settings.database_url)
    session = session_factory()
    store = ResearchStore(session)
    baseline = load_regression_baseline(args.baseline)
    try:
        report = run_deterministic_gate(
            settings=settings,
            store=store,
            db_session=session,
            fixture=fixture,
            baseline=baseline,
        )
    finally:
        session.close()

    if args.json:
        print(json.dumps(report_to_dict(report), indent=2))
    else:
        print(format_regression_report(report))

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
