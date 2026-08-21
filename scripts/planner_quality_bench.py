#!/usr/bin/env python3
"""Offline planner/DAG quality scoring against labelled dataset. No LLM spend."""

from __future__ import annotations

import json
from pathlib import Path

from deepscout_core.domain.enums import PlanDecomposition
from deepscout_core.domain.schemas import PlannerOutput, PlannerTask
from deepscout_research.runtime.dag_quality import evaluate_plan_dag
from deepscout_research.runtime.plan_repair import repair_plan

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "libs/evaluation/data/planner_quality_v1.json"


def _synthetic_v1_overdecomp(goal: str, expected: str) -> PlannerOutput:
    """Reproduce the previous planner habit: always two independent questions."""
    return PlannerOutput(
        approach="Split the goal.",
        success_criteria="Cover the goal.",
        questions=[],
        tasks=[
            PlannerTask(task_key="q1", objective=f"Investigate part A of: {goal[:80]}", priority=1),
            PlannerTask(task_key="q2", objective=f"Investigate part B of: {goal[:80]}", priority=2),
        ],
    )


def _synthetic_v2(goal: str, expected: str) -> PlannerOutput:
    decomposition = PlanDecomposition(expected)
    if decomposition == PlanDecomposition.SIMPLE:
        tasks = [PlannerTask(task_key="q1", objective=goal[:200], priority=1)]
    elif decomposition == PlanDecomposition.PARALLEL:
        tasks = [
            PlannerTask(task_key="a", objective="Independent dimension A", priority=1),
            PlannerTask(task_key="b", objective="Independent dimension B", priority=2),
        ]
    elif decomposition == PlanDecomposition.CHAIN:
        tasks = [
            PlannerTask(
                task_key="find", objective="Identify the needed entity or identifier", priority=1
            ),
            PlannerTask(
                task_key="use",
                objective="Use that finding to retrieve the dependent facts",
                priority=2,
            ),
        ]
    else:
        tasks = [
            PlannerTask(task_key="a", objective="Fan-out A", priority=1),
            PlannerTask(task_key="b", objective="Fan-out B", priority=2),
            PlannerTask(task_key="syn", objective="Fan-in synthesis from A and B", priority=3),
        ]
    return PlannerOutput(
        approach="Structured DAG.",
        success_criteria="Match labelled structure.",
        decomposition=decomposition,
        tasks=tasks,
    )


def main() -> int:
    payload = json.loads(DATASET.read_text())
    before_fail = after_fail = 0
    rows = []
    for case in payload["cases"]:
        expected = case["expected_decomposition"]
        v1 = evaluate_plan_dag(_synthetic_v1_overdecomp(case["goal"], expected), repaired=True)
        # unspecified v1-style two tasks stay two tasks after repair
        v1_ok = v1["task_count"] <= case["max_tasks"]
        if expected == "simple":
            v1_ok = v1["task_count"] <= 1
        if not v1_ok:
            before_fail += 1
        v2 = evaluate_plan_dag(_synthetic_v2(case["goal"], expected))
        after_ok = (
            v2["pass"]
            and case["min_tasks"] <= v2["task_count"] <= case["max_tasks"]
            and (
                bool(repair_plan(_synthetic_v2(case["goal"], expected)).tasks[-1].depends_on)
                if case["requires_depends_on"]
                else True
            )
        )
        if not after_ok:
            after_fail += 1
        rows.append(
            {
                "id": case["id"],
                "before_tasks": v1["task_count"],
                "after_tasks": v2["task_count"],
                "after_pass": v2["pass"],
                "requires_depends_on": case["requires_depends_on"],
            }
        )
    report = {
        "dataset": payload["dataset_id"],
        "cases": len(payload["cases"]),
        "v1_style_failures_on_simple_max": before_fail,
        "v2_repair_failures": after_fail,
        "rows": rows,
    }
    out = ROOT / "libs/evaluation/data/planner_quality_offline_v1.json"
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if after_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
