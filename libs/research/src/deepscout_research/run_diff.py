"""Deterministic run comparison. Newer is not 'improved'."""

from __future__ import annotations

import hashlib
from uuid import UUID

from deepscout_core.domain.enums import DiffChangeKind, PlanDecomposition
from deepscout_core.domain.schemas import PlannerOutput, PlannerQuestion, PlannerTask
from deepscout_evaluation.run_evals import evaluate_research_run
from deepscout_persistence.store import ResearchStore

from deepscout_research.runtime.dag_quality import evaluate_plan_dag


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _classify(left: set[str], right: set[str]) -> dict[str, list[str]]:
    return {
        DiffChangeKind.ADDED.value: sorted(right - left),
        DiffChangeKind.REMOVED.value: sorted(left - right),
        DiffChangeKind.UNCHANGED.value: sorted(left & right),
    }


def compare_runs(store: ResearchStore, left_id: UUID, right_id: UUID) -> dict:
    if left_id == right_id:
        raise ValueError("cannot compare a run with itself")
    left = store.get_run(left_id)
    right = store.get_run(right_id)
    if left is None or right is None:
        raise LookupError("run not found")
    left_row = store.get_run_row(left_id)
    right_row = store.get_run_row(right_id)
    left_sources = {row.canonical_url: row for row in store.list_sources(left_id)}
    right_sources = {row.canonical_url: row for row in store.list_sources(right_id)}
    left_claims = {_hash(row.statement): row.statement for row in store.list_claims(left_id)}
    right_claims = {_hash(row.statement): row.statement for row in store.list_claims(right_id)}
    left_snaps = {row.content_hash for row in store.list_snapshots_for_run(left_id)}
    right_snaps = {row.content_hash for row in store.list_snapshots_for_run(right_id)}
    left_tasks = store.list_tasks(left_id)
    right_tasks = store.list_tasks(right_id)

    def _dag(tasks) -> dict:
        if not tasks:
            return {"task_count": 0, "edges": []}
        plan = PlannerOutput(
            approach="compare",
            success_criteria="compare",
            decomposition=PlanDecomposition.UNSPECIFIED,
            questions=[PlannerQuestion(text=task.objective, priority=task.priority) for task in tasks],
            tasks=[
                PlannerTask(
                    task_key=task.task_key,
                    objective=task.objective,
                    depends_on=list(task.depends_on),
                    priority=task.priority,
                    allowed_tools=list(task.allowed_tools),
                )
                for task in tasks
            ],
        )
        quality = evaluate_plan_dag(plan, repaired=False)
        return {
            "task_count": quality["task_count"],
            "critical_path_depth": quality["critical_path_depth"],
            "parallel_width": quality["parallel_width"],
            "edges": [
                {"task_key": task.task_key, "depends_on": list(task.depends_on), "status": task.status.value}
                for task in tasks
            ],
        }

    left_eval = evaluate_research_run(store, left_id)
    right_eval = evaluate_research_run(store, right_id)
    eval_diff = {}
    for key in sorted(set(left_eval) | set(right_eval)):
        lv = left_eval.get(key)
        rv = right_eval.get(key)
        eval_diff[key] = {"left": lv if lv is not None else "UNKNOWN", "right": rv if rv is not None else "UNKNOWN"}

    left_usage = store.get_usage_summary(left_id)
    right_usage = store.get_usage_summary(right_id)
    return {
        "left": {
            "id": str(left.id),
            "goal": left.goal,
            "status": left.status.value,
            "lineage_kind": getattr(left_row, "lineage_kind", "none") if left_row else "none",
            "parent_run_id": str(left_row.parent_run_id) if left_row and left_row.parent_run_id else None,
            "planner_version": (left_row.config_snapshot or {}).get("prompts", {}).get("planner")
            if left_row
            else None,
            "model": left.llm_model,
            "provider": left.llm_provider,
        },
        "right": {
            "id": str(right.id),
            "goal": right.goal,
            "status": right.status.value,
            "lineage_kind": getattr(right_row, "lineage_kind", "none") if right_row else "none",
            "parent_run_id": str(right_row.parent_run_id) if right_row and right_row.parent_run_id else None,
            "planner_version": (right_row.config_snapshot or {}).get("prompts", {}).get("planner")
            if right_row
            else None,
            "model": right.llm_model,
            "provider": right.llm_provider,
        },
        "sources": _classify(set(left_sources), set(right_sources)),
        "snapshots": _classify(left_snaps, right_snaps),
        "claims": {
            DiffChangeKind.ADDED.value: [right_claims[k] for k in sorted(set(right_claims) - set(left_claims))][:40],
            DiffChangeKind.REMOVED.value: [left_claims[k] for k in sorted(set(left_claims) - set(right_claims))][:40],
            DiffChangeKind.UNCHANGED.value: len(set(left_claims) & set(right_claims)),
        },
        "contradictions": {
            "left": len(store.list_contradictions(left_id)),
            "right": len(store.list_contradictions(right_id)),
        },
        "plan": {"left": _dag(left_tasks), "right": _dag(right_tasks)},
        "usage": {
            "left": {
                "total_tokens": left_usage.total_tokens,
                "cost_usd": left_usage.cost_usd,
                "cost_status": left_usage.cost_status.value,
            },
            "right": {
                "total_tokens": right_usage.total_tokens,
                "cost_usd": right_usage.cost_usd,
                "cost_status": right_usage.cost_status.value,
            },
        },
        "evaluation": eval_diff,
        "plan_diagnostics": {
            "left": (left_row.config_snapshot or {}).get("plan_diagnostics") if left_row else None,
            "right": (right_row.config_snapshot or {}).get("plan_diagnostics") if right_row else None,
        },
    }
