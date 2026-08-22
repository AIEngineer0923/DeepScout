"""Operator-only: generate bounded demo runs with env keys, then publish.

Never a public HTTP route. Uses operator provider env keys, not the user vault.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
from uuid import UUID

from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import DeploymentMode, Settings
from deepscout_persistence.identity import get_local_system
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from deepscout_research.demo.catalog import DEMO_CATALOG, curated_demo_budget
from deepscout_research.demo.export import build_presentation_bundle_from_run
from deepscout_research.demo.presentation import merge_presentation_into_public_demo
from deepscout_research.demo.publication import publish_demo
from deepscout_research.demo.quality import review_demo_candidate
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.search.tavily import TavilyWebSearchProvider

_DATA_DIR = (
    Path(__file__).resolve().parents[1]
    / "libs/research/src/deepscout_research/demo/presentation_data"
)


def _translate_it_bundle(en: dict, *, slug: str) -> dict:
    script = Path(__file__).resolve().parent / "operator_localize_demos.py"
    spec = importlib.util.spec_from_file_location("operator_localize_demos", script)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load operator_localize_demos")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._translate_bundle(en, provider="google", slug=slug)


def _write_presentation_bundles(store: ResearchStore, run_id: UUID, *, slug: str) -> None:
    en = build_presentation_bundle_from_run(store, run_id, slug=slug, locale="en")
    en_path = _DATA_DIR / f"{slug}.en.json"
    en_path.write_text(json.dumps(en, ensure_ascii=False, indent=2), encoding="utf-8")
    it = _translate_it_bundle(en, slug=slug)
    it_path = _DATA_DIR / f"{slug}.it.json"
    it_path.write_text(json.dumps(it, ensure_ascii=False, indent=2), encoding="utf-8")
    row = store.get_run_row(run_id)
    if row is not None:
        snap = dict(row.config_snapshot or {})
        public_demo = merge_presentation_into_public_demo(
            {**(snap.get("public_demo") or {}), "slug": slug},
            slug,
        )
        store.merge_config_snapshot(run_id, {"public_demo": public_demo})


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
    if result.final_status.value == "completed":
        _write_presentation_bundles(store, run.id, slug=item["slug"])
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
