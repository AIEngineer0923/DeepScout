"""Live runtime verification gate — full pipeline acceptance on current main."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta

import pytest
from deepscout_core.domain.budget import ResearchBudget
from deepscout_core.domain.enums import ResearchRunStatus, ResearchTaskStatus
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import Settings, get_settings
from deepscout_research.langsmith_env import configure_langsmith_env
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.phases.text_utils import locate_quote_in_content
from deepscout_research.search.tavily import TavilyWebSearchProvider

_FORBIDDEN_TRACE_PATTERNS = (
    re.compile(r"lsv2_[a-zA-Z0-9]{10,}"),
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),
    re.compile(r"GOOGLE_API_KEY"),
    re.compile(r"TAVILY_API_KEY"),
    re.compile(r"LANGSMITH_API_KEY"),
    re.compile(r"postgresql\+psycopg://"),
)


def _gate_settings() -> Settings | None:
    settings = get_settings()
    if settings.google_api_key is None:
        return None
    try:
        settings.require_tavily_api_key()
    except ValueError:
        return None
    if settings.langsmith_api_key is None:
        return None
    return settings


def _assert_trace_privacy(client, project_name: str, run_id: str) -> None:
    since = datetime.now(UTC) - timedelta(minutes=30)
    runs = list(
        client.list_runs(
            project_name=project_name,
            filter=f'and(eq(metadata_key, "research_run_id"), eq(metadata_value, "{run_id}"))',
            start_time=since,
            limit=20,
        )
    )
    if not runs:
        runs = list(client.list_runs(project_name=project_name, limit=10))
    assert runs, "Expected LangSmith runs for live gate"
    for run in runs[:5]:
        payload = {
            "name": run.name,
            "inputs": run.inputs,
            "outputs": run.outputs,
            "extra": run.extra,
        }
        serialized = json.dumps(payload, default=str)
        for pattern in _FORBIDDEN_TRACE_PATTERNS:
            assert not pattern.search(serialized), pattern.pattern


@pytest.mark.integration
@pytest.mark.postgres
def test_runtime_gate_full_pipeline(store, db_session) -> None:
    live = _gate_settings()
    if live is None:
        pytest.skip("GOOGLE_API_KEY, TAVILY_API_KEY, LANGSMITH_API_KEY required")

    live = live.model_copy(
        update={"research_workers_inline": True, "research_use_legacy_path": False}
    )
    run = store.create_run(
        ResearchRunCreate(
            goal="Compare NMC and LFP EV battery chemistries with one trade-off.",
            budget=ResearchBudget(
                max_iterations=2,
                max_tool_calls=10,
                max_sources=8,
                max_total_tokens=30_000,
            ),
        ),
        live,
    )
    store.commit()

    with TavilyWebSearchProvider(live) as search:
        orchestrator = ResearchOrchestrator(store, live, search)
        result = orchestrator.execute(run.id)
    store.commit()

    refreshed = store.get_run(run.id)
    assert refreshed is not None
    assert result.final_status == ResearchRunStatus.COMPLETED

    tasks = store.list_tasks(run.id)
    assert len(tasks) >= 1
    assert any(task.status == ResearchTaskStatus.COMPLETED for task in tasks)

    sources = store.list_sources(run.id)
    assert len(sources) >= 1

    snapshots = sum(
        1 for source in sources if store.get_latest_snapshot_for_source(source.id) is not None
    )
    assert snapshots >= 1, "Expected at least one SourceSnapshot from secure fetch"

    claims = store.list_claims(run.id)
    evidence = store.list_evidence(run.id)
    assert len(claims) >= 1, "Expected extracted claims"
    assert len(evidence) >= 1, "Expected evidence rows"

    for item in evidence:
        snapshot = store.get_snapshot(item.snapshot_id)
        assert snapshot is not None
        resolved = locate_quote_in_content(item.quote, snapshot.content_text)
        assert resolved is not None, "Evidence quote must resolve in snapshot text"

    usage = store.get_usage_summary(run.id)
    token_rows = store.list_token_usage(run.id)
    assert token_rows, "Expected token usage records from planner/synthesis LLM calls"
    assert usage.total_tokens is not None and usage.total_tokens > 0
    assert any(row.input_tokens is not None for row in token_rows)

    report_events = [
        event
        for event in store.list_run_events(run.id)
        if (event.payload or {}).get("phase") == "report"
    ]
    assert report_events, "Expected report phase events"
    assert any(event.event_type == "phase.completed" for event in report_events)

    from langsmith import Client

    configure_langsmith_env(live)
    client = Client()
    _assert_trace_privacy(client, live.langsmith_project, str(run.id))


@pytest.mark.integration
@pytest.mark.postgres
def test_runtime_gate_baseline_vs_multi_agent_metrics(store, db_session) -> None:
    live = _gate_settings()
    if live is None:
        pytest.skip("GOOGLE_API_KEY, TAVILY_API_KEY, LANGSMITH_API_KEY required")

    goal = "What is NMC battery chemistry?"
    budget = ResearchBudget(
        max_iterations=1,
        max_tool_calls=2,
        max_sources=3,
        max_total_tokens=8_000,
    )

    def _run(*, legacy: bool) -> dict[str, int | str]:
        settings = live.model_copy(
            update={
                "research_workers_inline": True,
                "research_use_legacy_path": legacy,
            }
        )
        created = store.create_run(ResearchRunCreate(goal=goal, budget=budget), settings)
        store.commit()
        with TavilyWebSearchProvider(settings) as search:
            orchestrator = ResearchOrchestrator(store, settings, search)
            outcome = orchestrator.execute(created.id)
        store.commit()
        return {
            "run_id": str(created.id),
            "status": outcome.final_status.value,
            "tasks": len(store.list_tasks(created.id)),
            "sources": len(store.list_sources(created.id)),
            "evidence": len(store.list_evidence(created.id)),
            "tokens": store.get_usage_summary(created.id).total_tokens or 0,
        }

    multi = _run(legacy=False)
    legacy = _run(legacy=True)
    assert multi["tasks"] >= 1
    assert multi["sources"] >= 0
    assert legacy["sources"] >= 0
    # Record comparative metrics without claiming winner — both must terminate coherently.
    assert multi["status"] in {"completed", "budget_exhausted"}
    assert legacy["status"] in {"completed", "budget_exhausted"}
