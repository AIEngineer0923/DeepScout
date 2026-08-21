#!/usr/bin/env python3
"""Re-run HITL + parallel cases after live defects were fixed."""

from __future__ import annotations

import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_runtime_live_closure import TAG, _goal, _snapshot_case
from deepscout_core.domain.budget import ResearchBudget
from deepscout_core.domain.enums import ResearchRunStatus, ReviewDecisionKind, ReviewReasonCode
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_persistence.session import dispose_all_engines, get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.hitl import HumanReviewService
from deepscout_research.langsmith_env import configure_langsmith_env
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.runtime.config_snapshot import build_config_snapshot
from deepscout_research.search.tavily import TavilyWebSearchProvider

OUT = Path(__file__).resolve().parents[1] / "libs/evaluation/data/agent_runtime_live_closure_v1.json"


def main() -> int:
    settings = configure_langsmith_env().model_copy(
        update={"research_workers_inline": False, "research_use_legacy_path": False}
    )
    store = ResearchStore(get_session_factory(settings.database_url)())
    extra: dict = {"rerun_at": datetime.now(UTC).isoformat()}
    with TavilyWebSearchProvider(settings) as search:
        def run_case(case: str, goal: str, budget: ResearchBudget, concurrency: int):
            snap = {**build_config_snapshot(settings), "benchmark": TAG, "case": case, "rerun": True}
            created = store.create_run(
                ResearchRunCreate(goal=_goal(case, goal), budget=budget, research_mode="quick"),
                settings,
                config_snapshot=snap,
            )
            row = store.get_run_row(created.id)
            if row is not None:
                row.concurrency_limit = concurrency
            store.commit()
            t0 = time.perf_counter()
            ResearchOrchestrator(store, settings, search).execute(created.id)
            store.commit()
            return _snapshot_case(
                store, created.id, {"latency_ms": int((time.perf_counter() - t0) * 1000), "concurrency": concurrency, "rerun": True}
            )

        b_goal = (
            "Compare LFP and NMC EV batteries across energy density, cycle life, "
            "and thermal safety as independent criteria."
        )
        extra["B1"] = run_case(
            "B1R",
            b_goal,
            ResearchBudget(max_iterations=2, max_wall_time_seconds=180, max_total_tokens=40_000, max_cost_usd=0.75, max_sources=12, max_tool_calls=6),
            1,
        )
        extra["B2"] = run_case(
            "B2R",
            b_goal,
            ResearchBudget(max_iterations=2, max_wall_time_seconds=180, max_total_tokens=40_000, max_cost_usd=0.75, max_sources=12, max_tool_calls=6),
            3,
        )
        extra["F"] = run_case(
            "FR",
            "Name one common EV battery chemistry.",
            ResearchBudget(max_iterations=2, max_wall_time_seconds=180, max_total_tokens=20_000, max_cost_usd=0.75, max_sources=8, max_tool_calls=1),
            1,
        )
        f = extra["F"]
        hitl = {"paused": f["status"] == "paused", "review_id": None}
        if f["status"] == "paused":
            rid = extra["F"]["run_id"]
            from uuid import UUID

            run_id = UUID(rid)
            session = store._session
            session.close()
            dispose_all_engines()
            store = ResearchStore(get_session_factory(settings.database_url)())
            pending = store.get_pending_review(run_id, ReviewReasonCode.BUDGET_EXTENSION)
            hitl["process_restart"] = pending is not None and store.get_run(run_id).status == ResearchRunStatus.PAUSED
            hitl["review_id"] = str(pending.id) if pending else None
            service = HumanReviewService(store, settings)
            first = service.resolve_review(run_id=run_id, review_id=pending.id, decision_kind=ReviewDecisionKind.APPROVE, source="api")
            second = service.resolve_review(run_id=run_id, review_id=pending.id, decision_kind=ReviewDecisionKind.APPROVE, source="api")
            store.commit()
            ResearchOrchestrator(store, settings, search).execute(run_id)
            store.commit()
            extra["F"] = _snapshot_case(
                store,
                run_id,
                {
                    "rerun": True,
                    "hitl": {
                        **hitl,
                        "first_applied": first.applied,
                        "second_applied": second.applied,
                        "resumed_status": store.get_run(run_id).status.value,
                    },
                },
            )
        else:
            extra["F"]["hitl"] = hitl
    payload = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    payload.setdefault("reruns", {})
    payload["reruns"]["after_hitl_and_allocation_fix"] = extra
    b1, b2 = extra["B1"], extra["B2"]
    payload["reruns"]["single_vs_parallel_after_fix"] = {
        "b1_run": b1["run_id"],
        "b2_run": b2["run_id"],
        "b1_overlap": b1["overlap"],
        "b2_overlap": b2["overlap"],
        "b1_workers": b1["workers"],
        "b2_workers": b2["workers"],
        "b1_latency_ms": b1.get("latency_ms"),
        "b2_latency_ms": b2.get("latency_ms"),
        "b1_status": b1["status"],
        "b2_status": b2["status"],
    }
    OUT.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"status": "RERUN", "B1": b1["run_id"], "B2": b2["run_id"], "F": extra["F"]["run_id"], "F_status": extra["F"]["status"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
