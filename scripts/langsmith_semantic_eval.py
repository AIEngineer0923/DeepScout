#!/usr/bin/env python3
"""Offline semantic LLM judges on a tiny versioned dataset.

Evaluation token/cost is recorded separately from application usage.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from deepscout_core.domain.enums import AgentRole
from deepscout_evaluation.semantic_judges import JUDGE_VERSION, RUBRICS, JudgeVerdict
from deepscout_research.langsmith_env import configure_langsmith_env
from deepscout_research.routing.model_router import ModelRouter
from langchain_core.messages import HumanMessage, SystemMessage


def _dataset_path() -> Path:
    return Path(__file__).resolve().parents[1] / "evals" / "semantic-offline-v1.json"


def _judge_one(model, case: dict) -> JudgeVerdict:
    rubric_id = str(case["judge"])
    rubric = RUBRICS[rubric_id]
    payload = {
        "goal": case.get("goal"),
        "output": case.get("output"),
        "reference": case.get("reference"),
        "rubric": rubric,
        "rubric_id": rubric_id,
        "evaluator_version": JUDGE_VERSION,
        "instructions": "Return the JudgeVerdict schema only. Do not include hidden chain-of-thought.",
    }
    structured = model.with_structured_output(JudgeVerdict)
    result = structured.invoke(
        [
            SystemMessage(
                content="You are a strict research evaluator. Score only from the provided rubric."
            ),
            HumanMessage(content=json.dumps(payload)),
        ]
    )
    if not isinstance(result, JudgeVerdict):
        result = JudgeVerdict.model_validate(result)
    return result.model_copy(update={"rubric_id": rubric_id, "evaluator_version": JUDGE_VERSION})


def main() -> int:
    settings = configure_langsmith_env()
    dataset = json.loads(_dataset_path().read_text())
    router = ModelRouter(settings)
    model, selection = router.build_chat_model(AgentRole.EVALUATOR)
    results = []
    for case in dataset["cases"]:
        verdict = _judge_one(model, case)
        results.append(
            {
                "id": case["id"],
                "judge": case["judge"],
                "expected": case["expected"],
                "actual": verdict.verdict,
                "score": verdict.score,
                "rationale": verdict.rationale,
                "match": verdict.verdict == case["expected"],
                "provider": selection.provider.value,
                "model": selection.model,
                "evaluator_version": JUDGE_VERSION,
            }
        )
    matched = sum(1 for item in results if item["match"])
    payload = {
        "status": "SEMANTIC_OFFLINE_LLM_JUDGES_COMPLETED",
        "dataset": dataset["dataset_id"],
        "evaluator_version": JUDGE_VERSION,
        "provider": selection.provider.value,
        "model": selection.model,
        "cases": len(results),
        "agreements": matched,
        "results": results,
        "evaluation_cost": "UNKNOWN",
        "note": "Evaluation spend is not mixed into application run cost. Exact dollars UNKNOWN unless usage metadata is mapped.",
        "experiment_prefix": f"deepscout-semantic-llm-{datetime.now(UTC).strftime('%Y%m%d')}",
    }
    try:
        if settings.langsmith_api_key is not None:
            from langsmith import Client

            Client()
            payload["langsmith"] = "client_ready"
    except Exception:
        payload["langsmith"] = "unavailable"
    print(json.dumps(payload, indent=2))
    return 0 if matched >= 6 else 2


if __name__ == "__main__":
    raise SystemExit(main())
