"""Record provider token usage from LangChain model responses."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from deepscout_core.domain.enums import AgentRole, CostReportStatus, ResearchPhase
from deepscout_core.domain.usage import TokenUsageRecord
from deepscout_core.settings import Settings
from deepscout_persistence.store import ResearchStore
from deepscout_research.prompts.spec import PromptSpec
from deepscout_research.routing.model_router import ModelSelection
from deepscout_research.usage.pricing import DEFAULT_PRICING_CATALOG
from langchain_core.messages import AIMessage


def _coerce_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def metadata_from_ai_message(message: AIMessage) -> dict[str, object]:
    metadata: dict[str, object] = {}
    usage = getattr(message, "usage_metadata", None)
    if isinstance(usage, dict):
        metadata.update(usage)
    response_meta = getattr(message, "response_metadata", None) or {}
    if isinstance(response_meta, dict):
        token_usage = response_meta.get("token_usage") or response_meta.get("usage_metadata")
        if isinstance(token_usage, dict):
            metadata.update(token_usage)
        usage_meta = response_meta.get("usage_metadata")
        if isinstance(usage_meta, dict):
            metadata.update(usage_meta)
    return metadata


def record_model_usage(
    store: ResearchStore,
    settings: Settings,
    *,
    message: AIMessage,
    run_id: UUID,
    phase: ResearchPhase,
    role: AgentRole,
    selection: ModelSelection,
    prompt: PromptSpec | None = None,
    task_id: UUID | None = None,
    worker_id: UUID | None = None,
    iteration: int | None = None,
    retry: int = 0,
) -> TokenUsageRecord:
    usage = TokenUsageRecord.from_provider_metadata(
        research_run_id=run_id,
        phase=phase,
        agent_role=role,
        provider=selection.provider.value,
        model=selection.model,
        metadata=metadata_from_ai_message(message),
        task_id=task_id,
        worker_id=worker_id,
        iteration=iteration,
        retry=retry,
    )
    catalog = DEFAULT_PRICING_CATALOG
    cost, cost_status = catalog.estimate_cost(usage)
    store.record_token_usage(usage, pricing_version=catalog.version)
    if cost is not None and cost_status != CostReportStatus.UNKNOWN:
        from deepscout_core.domain.enums import BudgetMetric

        store.record_budget_usage(
            run_id,
            BudgetMetric.COST,
            cost,
            note=f"{role.value}:{selection.model}",
        )
    _ = settings  # reserved for future provider-specific normalization hooks
    _ = prompt
    return usage


def langsmith_metadata(
    *,
    prompt: PromptSpec,
    selection: ModelSelection,
    run_id: UUID,
    task_id: UUID | None = None,
    worker_id: UUID | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        **prompt.trace_metadata(),
        "provider": selection.provider.value,
        "model": selection.model,
        "research_run_id": str(run_id),
    }
    if task_id is not None:
        payload["task_id"] = str(task_id)
    if worker_id is not None:
        payload["worker_id"] = str(worker_id)
    return payload
