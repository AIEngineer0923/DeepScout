#!/usr/bin/env python3
"""Upload agent-runtime benchmark cases to LangSmith when credentials exist."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from deepscout_research.langsmith_env import configure_langsmith_env

DATASET = "deepscout-agent-runtime-v1"
BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1] / "libs/evaluation/data/agent_runtime_benchmark_v1.json"
)


def _target(inputs: dict) -> dict:
    return {
        "case_id": inputs.get("id"),
        "category": inputs.get("category"),
        "channel_is_data": inputs.get("channel") not in {None, "task_objective"},
    }


def _evaluator(run, example) -> dict:
    outputs = run.outputs or {}
    inputs = example.inputs or {}
    if inputs.get("untrusted"):
        score = 1.0 if outputs.get("channel_is_data") else 0.0
        return {"key": "untrusted_is_data", "score": score}
    matched = 1.0 if outputs.get("case_id") == inputs.get("id") else 0.0
    return {"key": "case_present", "score": matched}


def main() -> int:
    settings = configure_langsmith_env()
    if settings.langsmith_api_key is None:
        print(json.dumps({"status": "SKIPPED", "reason": "LANGSMITH_API_KEY not configured"}))
        return 0

    payload = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    from langsmith import Client
    from langsmith.evaluation import evaluate

    client = Client()
    existing = list(client.list_datasets(dataset_name=DATASET))
    dataset = existing[0] if existing else client.create_dataset(
        DATASET,
        description="DeepScout agent-runtime structural cases v1",
    )
    if not existing:
        for case in payload["cases"]:
            client.create_example(
                inputs={
                    "id": case["id"],
                    "category": case["category"],
                    "objective": case.get("objective"),
                    "untrusted": case.get("untrusted"),
                    "channel": case.get("channel"),
                },
                outputs={"category": case["category"]},
                dataset_id=dataset.id,
            )

    prefix = f"agent-runtime-{datetime.now(UTC).strftime('%Y%m%d')}"
    evaluate(
        _target,
        data=DATASET,
        evaluators=[_evaluator],
        experiment_prefix=prefix,
        metadata={
            "dataset_version": payload["version"],
            "runtime": "current-main",
            "skills_enabled": settings.agent_skills_auto,
            "max_delegation_depth": settings.agent_max_delegation_depth,
            "max_replans": settings.agent_max_replans,
            "max_concurrency_hint": settings.agent_max_total_workers,
            "provider": settings.llm_provider.value,
            "model": settings.llm_model or "default",
            "reasoning_effort": settings.llm_reasoning_effort,
        },
        client=client,
    )
    print(json.dumps({"status": "PASS", "dataset": DATASET, "experiment_prefix": prefix}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
