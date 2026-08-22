"""Export publication-ready presentation bundles from completed research runs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from deepscout_persistence.store import ResearchStore

from deepscout_research.demo.catalog import DEMO_BY_SLUG
from deepscout_research.demo.presentation_validation import PRESENTATION_VERSION


def _worker_display_name(index: int, objective: str) -> str:
    words = [token.strip(".,:;()") for token in objective.split() if token.strip(".,:;()")]
    label = " ".join(words[:4]) or f"Task {index}"
    return f"W{index:02d} · {label}"


def build_presentation_bundle_from_run(
    store: ResearchStore,
    run_id: UUID,
    *,
    slug: str,
    locale: str = "en",
) -> dict[str, Any]:
    row = store.get_run_row(run_id)
    if row is None:
        raise LookupError("run not found")
    meta = DEMO_BY_SLUG.get(slug, {})
    tasks = store.list_tasks(run_id)
    claims = store.list_claims(run_id)
    report = store.get_report(run_id)

    task_overlays: dict[str, dict[str, str]] = {}
    worker_overlays: dict[str, dict[str, str]] = {}
    for index, task in enumerate(tasks, start=1):
        display = _worker_display_name(index, task.objective)
        task_overlays[task.task_key] = {
            "objective": task.objective,
            "display_name": display,
        }
        if task.worker_id:
            worker_overlays[str(task.worker_id)] = {
                "display_name": display,
                "assigned_task": task.objective,
            }

    claim_overlays = {str(claim.id): claim.statement for claim in claims}
    report_body = (report.body_markdown if report else "") or ""
    report_title = (report.title if report else "") or meta.get("title", "Research Report")

    return {
        "version": PRESENTATION_VERSION,
        "locale": locale,
        "run_id": str(run_id),
        "goal": meta.get("goal") or row.goal,
        "title": meta.get("title") or report_title,
        "summary": meta.get("summary") or report_title[:160],
        "why_interesting": meta.get("why_interesting") or meta.get("summary") or "",
        "tasks": task_overlays,
        "workers": worker_overlays,
        "report": {
            "title": report_title,
            "body_markdown": report_body,
        },
        "claims": claim_overlays,
    }
