"""Operator-only: generate bounded demo runs with env keys, then publish.

Never a public HTTP route. Uses operator provider env keys, not the user vault.
"""

from __future__ import annotations

import argparse
import json
import os

from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import DeploymentMode, Settings
from deepscout_persistence.identity import get_local_system
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.demo.catalog import DEMO_CATALOG, curated_demo_budget
from deepscout_research.demo.publication import publish_demo
from deepscout_research.demo.quality import review_demo_candidate
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.search.tavily import TavilyWebSearchProvider


def _run_one(
    store: ResearchStore,
    settings: Settings,
    owner_id,
    item: dict,
    *,
    auto_publish: bool,
) -> dict:
    mode = item.get("research_mode", "standard")
    run = store.create_run(
        ResearchRunCreate(
            goal=item["goal"],
            research_mode=mode,
            output_language="en",
            budget=curated_demo_budget(mode),
        ),
        settings,
        owner_principal_id=owner_id,
    )
    store.commit()
    with TavilyWebSearchProvider(settings) as search:
        orch = ResearchOrchestrator(store, settings, search)
        result = orch.execute(run.id)
    usage = store.get_usage_summary(run.id)
    review = review_demo_candidate(store, run.id, slug=item["slug"])
    published = False
    if (
        result.final_status.value == "completed"
        and auto_publish
        and review["PUBLICATION_DECISION"] == "PASS"
    ):
        publish_demo(store, run.id, item["slug"])
        published = True
    store.commit()
    return {
        "slug": item["slug"],
        "run_id": str(run.id),
        "status": result.final_status.value,
        "published": published,
        "quality": review["PUBLICATION_DECISION"],
        "reason_codes": review.get("reason_codes", []),
        "warnings": review.get("warnings", []),
        "tokens": usage.total_tokens,
        "cost_usd": usage.cost_usd,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only-slug")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--auto-publish",
        action="store_true",
        help="Publish only when quality gate returns PASS",
    )
    args = parser.parse_args()
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["DEEPSCOUT_DEPLOYMENT_MODE"] = "local"
    os.environ["RESEARCH_WORKERS_INLINE"] = "true"
    settings = Settings().model_copy(
        update={
            "deployment_mode": DeploymentMode.LOCAL,
            "research_workers_inline": True,
            "research_use_legacy_path": False,
        }
    )
    selected = [
        item for item in DEMO_CATALOG if args.only_slug is None or item["slug"] == args.only_slug
    ]
    if args.dry_run:
        print(json.dumps({"would_run": [item["slug"] for item in selected]}, indent=2))
        return 0
    session = get_session_factory(settings.database_url)()
    store = ResearchStore(session)
    owner = get_local_system(session)
    store.commit()
    results = []
    try:
        for item in selected:
            results.append(
                _run_one(store, settings, owner.id, item, auto_publish=args.auto_publish)
            )
    finally:
        session.close()
    print(json.dumps({"candidates": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
