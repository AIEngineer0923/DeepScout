#!/usr/bin/env python3
"""Deterministic learning-loop CI gate — zero provider spend."""

from __future__ import annotations

import argparse
import json
import sys

from deepscout_evaluation.learning.loop import run_learning_loop_gate


def main() -> int:
    parser = argparse.ArgumentParser(description="Run learning loop deterministic gate")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()
    report = run_learning_loop_gate()
    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        for item in report.cases:
            status = "PASS" if item.passed else "FAIL"
            print(f"[{status}] {item.case_id} ({item.stage}) {item.detail}")
        print(f"\nOverall: {'PASS' if report.passed else 'FAIL'}")
    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
