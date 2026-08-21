"""Create one bounded persisted research run for UI inspection. Does not roll back."""

from __future__ import annotations

import json
import sys

from deepscout_core.domain.budget import ResearchBudget
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.langsmith_env import configure_langsmith_env
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.search.tavily import TavilyWebSearchProvider


def main() -> int:
    settings = configure_langsmith_env()
    settings = settings.model_copy(
        update={"research_workers_inline": True, "research_use_legacy_path": False}
    )
    session = get_session_factory(settings.database_url)()
    store = ResearchStore(session)
    goal = (
        sys.argv[1] if len(sys.argv) > 1 else "Compare NMC and LFP EV batteries in one paragraph."
    )
    run = store.create_run(
        ResearchRunCreate(
            goal=goal,
            research_mode="quick",
            output_language="en",
            budget=ResearchBudget(
                max_iterations=1,
                max_wall_time_seconds=180,
                max_total_tokens=40_000,
                max_cost_usd=1.0,
                max_sources=4,
                max_tool_calls=8,
            ),
        ),
        settings,
    )
    store.commit()
    with TavilyWebSearchProvider(settings) as search:
        orch = ResearchOrchestrator(store, settings, search)
        result = orch.execute(run.id)
    store.commit()
    usage = store.get_usage_summary(run.id)
    print(
        json.dumps(
            {
                "run_id": str(run.id),
                "status": result.final_status.value,
                "goal": goal,
                "application_tokens": usage.total_tokens,
                "application_cost_usd": usage.cost_usd,
                "evaluation_cost_usd": usage.evaluation_cost_usd,
            }
        )
    )
    session.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
