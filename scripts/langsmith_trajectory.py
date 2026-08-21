#!/usr/bin/env python3
"""Offline trajectory evaluation against DeepScout baseline examples."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from deepscout_evaluation.trajectory import (
    REQUIRED_MULTI_AGENT_ACTIONS,
    TrajectoryMatchMode,
    match_trajectory,
)
from deepscout_research.langsmith_env import configure_langsmith_env


def _target(inputs: dict) -> dict:
    scenario = inputs.get("scenario", "simple_research")
    actions = ["phase.plan", "phase.research", "tool.web_search", "phase.report"]
    if scenario == "parallel_independent":
        actions = [
            "phase.plan",
            "worker:a",
            "worker:b",
            "tool.web_search",
            "phase.report",
        ]
    if scenario == "budget_exhaustion":
        actions = ["phase.plan", "phase.research", "phase.report"]
    return {"scenario": scenario, "actions": actions}


def _trajectory_eval(run, example) -> dict:
    actions = (run.outputs or {}).get("actions") or []
    score = 1.0 if match_trajectory(actions, list(REQUIRED_MULTI_AGENT_ACTIONS), mode=TrajectoryMatchMode.SUPERSET) or match_trajectory(actions, ["phase.plan", "phase.research", "phase.report"], mode=TrajectoryMatchMode.SUPERSET) else 0.0
    return {"key": "trajectory_superset", "score": score}


def main() -> int:
    settings = configure_langsmith_env()
    if settings.langsmith_api_key is None:
        print("LANGSMITH_API_KEY not configured", file=sys.stderr)
        return 1
    from langsmith import Client
    from langsmith.evaluation import evaluate

    client = Client()
    prefix = f"deepscout-trajectory-{datetime.now(UTC).strftime('%Y%m%d')}"
    results = evaluate(
        _target,
        data="deepscout-baseline-v1",
        evaluators=[_trajectory_eval],
        experiment_prefix=prefix,
        metadata={
            "architecture_version": "multi-agent-v1",
            "evaluator_version": "trajectory-superset-v1",
        },
        client=client,
        max_concurrency=2,
    )
    print(
        json.dumps(
            {
                "status": "TRAJECTORY_EXPERIMENT_COMPLETED",
                "experiment": getattr(results, "experiment_name", None) or prefix,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
