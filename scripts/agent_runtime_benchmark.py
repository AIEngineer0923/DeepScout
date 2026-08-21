#!/usr/bin/env python3
"""Agent-runtime benchmark v1 — structural measurements, no invented quality scores."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from deepscout_core.domain.enums import ResearchTaskStatus
from deepscout_core.domain.schemas import ResearchTaskRead
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_evaluation.runtime_replay import reconstruct_decisions
from deepscout_evaluation.runtime_trajectory import (
    eval_allocation_does_not_maximize_agents,
    eval_single_ready_is_single_worker,
    eval_untrusted_channel_binds_no_skills,
)
from deepscout_research.runtime.allocation import allocate_workers
from deepscout_research.runtime.compaction import compact_retrieved
from deepscout_research.runtime.delegation import DelegationPolicy
from deepscout_research.runtime.replan import evaluate_replan
from deepscout_research.skills.router import select_skills
from deepscout_research.tools.registry import classify_tool_request

BENCHMARK_PATH = (
    Path(__file__).resolve().parents[1] / "libs/evaluation/data/agent_runtime_benchmark_v1.json"
)


def _settings() -> Settings:
    return Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE)


def _task(
    key: str,
    deps: list[str],
    *,
    status: ResearchTaskStatus = ResearchTaskStatus.READY,
) -> ResearchTaskRead:
    return ResearchTaskRead(
        id=uuid4(),
        task_key=key,
        objective=f"Investigate {key}",
        status=status,
        priority=1,
        depends_on=deps,
        allowed_tools=["web_search"],
    )


def _llm_stub_compact(items: list[str], char_limit: int) -> tuple[list[str], list[str], int]:
    """Simulated LLM summary compaction: strips artifact ids. Risk probe only."""
    import re

    pattern = r"\b(?:snapshot|claim|evidence|source):[0-9a-f-]{8,}\b"
    stripped = [re.sub(pattern, "", item, flags=re.I) for item in items]
    joined = " ".join(item[:80] for item in stripped)
    summary = ("Generated overview without provenance: " + joined)[:char_limit]
    return [summary], [], max(0, len(items) - 1)


def main() -> int:
    payload = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    settings = _settings()
    policy = DelegationPolicy.from_settings(settings)
    results: list[dict[str, object]] = []

    for case in payload["cases"]:
        row: dict[str, object] = {"id": case["id"], "category": case["category"]}
        if "dag" in case:
            tasks = [_task(node["key"], node["deps"]) for node in case["dag"]]
            remaining = int(case.get("remaining_tool_calls", 20))
            decision = allocate_workers(
                tasks,
                settings=settings,
                concurrency_limit=4,
                remaining_tool_calls=remaining,
            )
            row["allocation_class"] = decision.allocation_class.value
            row["max_workers"] = decision.max_workers
            row["ready_count"] = decision.ready_count
            row["allocation_ok"] = eval_allocation_does_not_maximize_agents(
                decision, ready_count=decision.ready_count
            ) and eval_single_ready_is_single_worker(decision)
            expected = case.get("expect_allocation")
            matched = expected is None or decision.allocation_class.value == expected
            row["allocation_match"] = matched
        if "skill_objective" in case:
            selected = select_skills(case["skill_objective"], channel="task_objective")
            ids = [skill.skill_id for skill in selected]
            row["skills"] = ids
            expected_skill = case.get("expect_skill")
            row["skill_match"] = (not expected_skill and not ids) or expected_skill in ids
        if "untrusted" in case:
            channel = str(case.get("channel", "retrieved_document"))
            row["untrusted_binds_no_skill"] = eval_untrusted_channel_binds_no_skills(
                case["untrusted"], channel
            )
            row["spawn_blocked"] = not policy.can_delegate(
                parent_depth=0,
                existing_children=0,
                total_workers=1,
                untrusted_text=case["untrusted"],
            )
            row["shell_denied"] = classify_tool_request("shell") == "deny"
        if case.get("failed_task") is True:
            failed = _task("q1", [], status=ResearchTaskStatus.FAILED)
            decision = evaluate_replan(
                settings=settings,
                replans_used=0,
                tasks=[failed],
                last_batch_sources=0,
                evidence_count=0,
            )
            row["replan_apply"] = decision.apply
            row["replan_match"] = decision.apply is bool(case.get("expect_replan"))
        elif case.get("failed_task") is False:
            done = _task("q1", [], status=ResearchTaskStatus.COMPLETED)
            decision = evaluate_replan(
                settings=settings,
                replans_used=0,
                tasks=[done],
                last_batch_sources=2,
                evidence_count=3,
            )
            row["replan_apply"] = decision.apply
            row["replan_match"] = decision.apply is False
        results.append(row)

    constraint = "snapshot:aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee KEEP_ME"
    long_items = [f"{constraint} {'x' * 4000}", f"{constraint} {'x' * 4000}", "noise " * 200]
    det, refs, dropped = compact_retrieved(long_items, char_limit=800)
    stub, stub_refs, _ = _llm_stub_compact(long_items, 800)
    compaction = {
        "deterministic_dropped": dropped,
        "deterministic_keeps_ref": any("snapshot:" in item for item in det + refs),
        "llm_stub_keeps_ref": any("snapshot:" in item for item in stub + stub_refs),
        "llm_stub_tokens_shorter": len("".join(stub)) <= len("".join(det)),
    }
    replay = reconstruct_decisions(
        [
            {"event_type": "workers.allocated", "payload": {"reason": "few_independent_tasks"}},
            {"event_type": "replan.applied", "payload": {"reason": "failed_tasks_need_gap_fill"}},
        ]
    )

    allocation_ok = all(item.get("allocation_ok", True) for item in results)
    allocation_match = all(item.get("allocation_match", True) for item in results)
    skill_match = all(item.get("skill_match", True) for item in results)
    untrusted_ok = all(item.get("untrusted_binds_no_skill", True) for item in results)
    spawn_ok = all(
        item.get("spawn_blocked")
        for item in results
        if item.get("category")
        in {"ADVERSARIAL", "AGENT_SPAWN_INJECTION", "PROMPT_INJECTED_SOURCE"}
    )
    replan_ok = all(item.get("replan_match", True) for item in results)

    report = {
        "status": "PASS"
        if all([allocation_ok, allocation_match, skill_match, untrusted_ok, spawn_ok, replan_ok])
        and compaction["deterministic_keeps_ref"]
        and not compaction["llm_stub_keeps_ref"]
        else "WARN",
        "dataset": payload["version"],
        "case_count": len(results),
        "allocation_ok": allocation_ok,
        "allocation_match": allocation_match,
        "skill_match": skill_match,
        "untrusted_ok": untrusted_ok,
        "spawn_ok": spawn_ok,
        "replan_ok": replan_ok,
        "compaction": compaction,
        "replay_events_reconstructed": len(replay),
        "promotion_hints": {
            "delegated_budget": "KEEP_DEFERRED — global FOR UPDATE already caps the run",
            "max_depth_gt_1": "KEEP_DEFERRED — DAG parallelizes independent work",
            "llm_compaction": "KEEP_DEFERRED — stub loses snapshot refs",
            "reasoning_effort": "IMPLEMENTED_OPTIONAL — capability allowlist, default unset",
            "prompt_cache_instrumentation": (
                "IMPLEMENTED_DEFAULT — parse provider cache_read fields"
            ),
            "dynamic_skills": "REJECT auto-promote / KEEP_DEFERRED generation",
            "semantic_skill_judges": "KEEP_DEFERRED",
            "online_eval_dataset": "KEEP_DEFERRED — privacy",
            "playwright_runtime_e2e": "IMPLEMENTED_DEFAULT — fixture suite",
            "finalization_reserve": (
                "KEEP_DEFERRED — ADR-007 already finalizes after research budget"
            ),
            "langgraph_time_travel_ui": "KEEP_DEFERRED — domain fork is the product path",
            "generic_long_term_memory": "REJECT",
            "semantic_answer_cache": "REJECT",
        },
        "cases": results,
    }
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
