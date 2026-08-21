#!/usr/bin/env python3
"""Live planner chain gate — persisted DAG must encode dependency even if first label is SIMPLE."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from deepscout_core.settings import Settings
from deepscout_research.planner import build_research_plan
from deepscout_research.runtime.dependency_validator import LAST_DIAGNOSTICS

OUT = Path("libs/evaluation/data/planner_chain_live_v1.json")
GOALS = [
    "Identify the current UN Secretary-General, then determine the statutory duties of the person identified.",
    "Identify the current WHO Director-General, then report that person's appointment process.",
    "Identify the current US Poet Laureate, then list that person's most recent published collection.",
]


def main() -> int:
    settings = Settings()
    if settings.google_api_key is None and settings.openai_api_key is None and settings.anthropic_api_key is None:
        OUT.write_text(json.dumps({"skipped": True, "reason": "no LLM credentials"}) + "\n")
        print("SKIP: no LLM credentials")
        return 0
    rows = []
    for goal in GOALS:
        plan = build_research_plan(
            settings,
            run_id=uuid4(),
            goal=goal,
            budget_summary="iterations=2, sources=8, tool_calls=8",
        )
        edges = [{"task_key": t.task_key, "depends_on": list(t.depends_on)} for t in plan.tasks]
        rows.append(
            {
                "goal": goal,
                "decomposition": plan.decomposition.value,
                "task_count": len(plan.tasks),
                "edges": edges,
                "has_dependency": any(t.depends_on for t in plan.tasks),
                "diagnostics": dict(LAST_DIAGNOSTICS),
            }
        )
    passed = all(item["has_dependency"] for item in rows)
    payload = {"pass": passed, "cases": rows}
    OUT.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
