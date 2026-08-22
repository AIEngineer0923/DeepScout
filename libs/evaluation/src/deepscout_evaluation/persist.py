"""Persist evaluation rows for completed research runs."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.domain.enums import TERMINAL_RESEARCH_RUN_STATUSES
from deepscout_persistence.store import ResearchStore

from deepscout_evaluation.matrix import build_evaluation_rows
from deepscout_evaluation.run_evals import evaluate_research_run


def persist_research_evaluations(store: ResearchStore, run_id: UUID) -> list[dict[str, object]]:
    rows = build_evaluation_rows(evaluate_research_run(store, run_id))
    store.replace_evaluation_results(run_id, rows)
    try:
        from deepscout_evaluation.learning.experience_store import observe_and_persist_terminal_run

        observe_and_persist_terminal_run(store, run_id)
    except Exception:
        pass
    return rows


def load_evaluation_rows(
    store: ResearchStore,
    run_id: UUID,
    *,
    include_evals: bool,
    backfill: bool = True,
) -> list[dict[str, object]]:
    run = store.get_run(run_id)
    if run is None:
        raise LookupError(f"ResearchRun {run_id} not found")
    if not include_evals:
        return []
    persisted = store.list_evaluation_results(run_id)
    if persisted:
        return persisted
    if run.status not in TERMINAL_RESEARCH_RUN_STATUSES:
        return []
    rows = build_evaluation_rows(evaluate_research_run(store, run_id))
    if backfill:
        store.replace_evaluation_results(run_id, rows)
    return rows
