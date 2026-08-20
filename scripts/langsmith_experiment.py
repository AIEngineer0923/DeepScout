#!/usr/bin/env python3
"""Run LangSmith baseline bootstrap and a lightweight offline experiment."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime

from deepscout_research.langsmith_env import configure_langsmith_env


def _scenario_evaluator(run, example) -> dict:
    """Deterministic offline evaluator — no LLM judge."""
    outputs = run.outputs or {}
    expected = example.outputs or {}
    scenario = (example.inputs or {}).get("scenario")
    score = 1.0 if outputs.get("scenario") == scenario else 0.0
    if "expected_evidence_min" in expected:
        score = min(
            score,
            1.0 if outputs.get("evidence_count", 0) >= expected["expected_evidence_min"] else 0.0,
        )
    return {"key": "scenario_contract", "score": score}


def _offline_target(inputs: dict) -> dict:
    """Export scenario metadata for offline dataset experiments (no provider calls)."""
    scenario = inputs.get("scenario", "unknown")
    evidence_min = 0
    if scenario in {"simple_research", "parallel_independent", "dependent_research"}:
        evidence_min = 1
    return {
        "scenario": scenario,
        "evidence_count": evidence_min,
        "architecture_version": "multi-agent-v1",
        "prompt_versions": {"planner": "1", "synthesis": "1"},
    }


def main() -> int:
    settings = configure_langsmith_env()
    if settings.langsmith_api_key is None:
        print("LANGSMITH_API_KEY not configured", file=sys.stderr)
        return 1

    bootstrap = subprocess.run(
        [sys.executable, "scripts/langsmith_bootstrap.py"],
        check=False,
        capture_output=True,
        text=True,
    )
    print(bootstrap.stdout.strip() or bootstrap.stderr.strip())
    if bootstrap.returncode != 0:
        return bootstrap.returncode

    from langsmith import Client
    from langsmith.evaluation import evaluate

    client = Client()
    datasets = list(client.list_datasets(dataset_name="deepscout-baseline-v1"))
    if not datasets:
        print(json.dumps({"status": "BLOCKED", "reason": "dataset_missing"}))
        return 1
    dataset = datasets[0]
    experiment_prefix = f"deepscout-gate-{datetime.now(UTC).strftime('%Y%m%d')}"
    results = evaluate(
        _offline_target,
        data=dataset.name,
        evaluators=[_scenario_evaluator],
        experiment_prefix=experiment_prefix,
        metadata={
            "architecture_version": "multi-agent-v1",
            "dataset_version": dataset.name,
            "evaluator_version": "deterministic-scenario-v1",
            "provider": settings.llm_provider.value,
            "model": settings.llm_model or "default",
        },
        client=client,
        max_concurrency=2,
    )
    experiment_name = getattr(results, "experiment_name", None) or experiment_prefix
    print(
        json.dumps(
            {
                "status": "EXPERIMENT_COMPLETED",
                "dataset": dataset.name,
                "dataset_id": str(dataset.id),
                "experiment": experiment_name,
                "experiment_prefix": experiment_prefix,
                "evaluator": "deterministic-scenario-v1",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
