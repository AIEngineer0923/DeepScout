"""Operator-only: generate bounded demo runs with env keys, then publish.

Never a public HTTP route. Uses operator provider env keys, not the user vault.
"""

from __future__ import annotations

import argparse
import json
import os
import re

from deepscout_core.domain.budget import ResearchBudget
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import Settings
from deepscout_persistence.identity import get_local_system
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.demo.publication import publish_demo
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.search.tavily import TavilyWebSearchProvider

DEMOS = (
    {
        "slug": "event-driven-research-runtime",
        "goal": (
            "Compare event-driven workers versus request/response APIs "
            "for long-running research jobs."
        ),
    },
    {
        "slug": "mrna-vaccine-durability",
        "goal": "Summarize current scientific evidence on mRNA vaccine antibody durability.",
    },
    {
        "slug": "eu-ai-act-gpaI",
        "goal": "Explain how the EU AI Act classifies general-purpose AI systems for providers.",
    },
)

_REDACT = (
    re.compile(r"/Users/[^\s]+"),
    re.compile(r"/home/[^\s]+"),
    re.compile(r"localhost:\d+"),
    re.compile(r"127\.0\.0\.1"),
)


def _sanitize(text: str) -> str:
    out = text
    for pattern in _REDACT:
        out = pattern.sub("[redacted]", out)
    return out


def _run_one(store: ResearchStore, settings: Settings, owner_id, item: dict) -> dict:
    run = store.create_run(
        ResearchRunCreate(
            goal=item["goal"],
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
        owner_principal_id=owner_id,
    )
    store.commit()
    with TavilyWebSearchProvider(settings) as search:
        orch = ResearchOrchestrator(store, settings, search)
        result = orch.execute(run.id)
    if result.final_status.value != "completed":
        store.commit()
        usage = store.get_usage_summary(run.id)
        return {
            "slug": item["slug"],
            "run_id": str(run.id),
            "status": result.final_status.value,
            "published": False,
            "tokens": usage.total_tokens,
            "cost_usd": usage.cost_usd,
        }
    report = store.get_report(run.id)
    if report is not None and report.body_markdown:
        report.body_markdown = _sanitize(report.body_markdown)
        report.title = _sanitize(report.title)
    publish_demo(store, run.id, item["slug"])
    store.commit()
    usage = store.get_usage_summary(run.id)
    return {
        "slug": item["slug"],
        "run_id": str(run.id),
        "status": result.final_status.value,
        "tokens": usage.total_tokens,
        "cost_usd": usage.cost_usd,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-slug")
    args = parser.parse_args()
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["DEEPSCOUT_DEPLOYMENT_MODE"] = "local"
    settings = Settings()
    session = get_session_factory(settings.database_url)()
    store = ResearchStore(session)
    owner = get_local_system(session)
    store.commit()
    selected = [item for item in DEMOS if args.only_slug is None or item["slug"] == args.only_slug]
    results = []
    try:
        for item in selected:
            results.append(_run_one(store, settings, owner.id, item))
    finally:
        session.close()
    print(json.dumps({"published": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
