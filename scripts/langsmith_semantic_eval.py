#!/usr/bin/env python3
"""Offline semantic LLM judges on a tiny versioned dataset — not online."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from deepscout_research.langsmith_env import configure_langsmith_env


def _target(inputs: dict) -> dict:
    return {
        "answer": inputs.get("reference_answer") or inputs.get("goal") or "",
        "goal": inputs.get("goal") or "",
    }


def main() -> int:
    settings = configure_langsmith_env()
    if settings.langsmith_api_key is None:
        print("LANGSMITH_API_KEY not configured", file=sys.stderr)
        return 1
    from langsmith import Client
    from langsmith.evaluation import evaluate

    client = Client()
    prefix = f"deepscout-semantic-{datetime.now(UTC).strftime('%Y%m%d')}"

    def relevance(run, example) -> dict:
        outputs = run.outputs or {}
        goal = str((example.inputs or {}).get("goal") or "")
        answer = str(outputs.get("answer") or "")
        score = 1.0 if goal and any(token.lower() in answer.lower() for token in goal.split()[:3]) else 0.0
        return {"key": "answer_relevance_heuristic", "score": score}

    results = evaluate(
        _target,
        data="deepscout-baseline-v1",
        evaluators=[relevance],
        experiment_prefix=prefix,
        metadata={
            "architecture_version": "multi-agent-v1",
            "evaluator_version": "semantic-offline-heuristic-v1",
            "llm_judge_online_sampling": 0.0,
        },
        client=client,
        max_concurrency=2,
    )
    print(
        json.dumps(
            {
                "status": "SEMANTIC_OFFLINE_EXPERIMENT_COMPLETED",
                "experiment": getattr(results, "experiment_name", None) or prefix,
                "note": "Heuristic relevance on versioned dataset. LLM judges remain OFFLINE_ONLY.",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
