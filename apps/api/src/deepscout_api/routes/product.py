"""Dashboard and settings read models — no fake billing or user accounts."""

from __future__ import annotations

from deepscout_core.settings import Settings, get_settings
from deepscout_core.types import ProviderKind
from deepscout_providers.defaults import DEFAULT_EMBEDDING_MODELS
from fastapi import APIRouter, Depends

from deepscout_api.deps import get_research_store
from deepscout_api.probes import probe_postgres
from deepscout_api.routes.research_runs import _list_item

router = APIRouter(prefix="/api/v1", tags=["product"])


@router.get("/overview")
def product_overview(
    store=Depends(get_research_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    rows, total = store.list_runs(limit=100, offset=0)
    metrics = store.list_run_card_metrics([row.id for row in rows])
    cards = [_list_item(row, metrics[row.id]) for row in rows]
    items = cards[:8]
    active = next((item for item in items if item.status in {"running", "pending"}), None)
    known_costs = [item.cost_usd for item in cards if item.cost_usd is not None]
    completed = [item for item in cards if item.status == "completed" and item.started_at and item.completed_at]
    durations = []
    for item in completed[-10:]:
        durations.append((item.completed_at - item.started_at).total_seconds())
    return {
        "active": active.model_dump(mode="json") if active else None,
        "recent": [item.model_dump(mode="json") for item in items],
        "totals": {
            "runs": total,
            "sources": sum(item.source_count for item in cards),
            "evidence": sum(item.evidence_count for item in cards),
            "claims": sum(item.claim_count for item in cards),
            "known_cost_usd": round(sum(known_costs), 4) if known_costs else None,
            "cost_status": "estimated" if known_costs else "unknown",
            "avg_completion_seconds": round(sum(durations) / len(durations), 1) if durations else None,
        },
        "identity": {"label": "Local workspace", "role": "Operator"},
        "langsmith": _langsmith_status(settings),
        "providers": _provider_status(settings),
    }


@router.get("/settings")
def product_settings(settings: Settings = Depends(get_settings)) -> dict:
    postgres = probe_postgres(settings.database_url)
    return {
        "identity": {"label": "Local workspace", "role": "Operator", "plan": None},
        "providers": _provider_status(settings),
        "langsmith": _langsmith_status(settings),
        "research_defaults": {
            "max_iterations": settings.research_max_iterations,
            "max_sources": settings.research_max_sources,
            "max_tool_calls": settings.research_max_tool_calls,
            "max_wall_time_seconds": settings.research_max_wall_time_s,
            "concurrency_note": "Worker fan-out is bounded by run concurrency_limit (default 3).",
            "durable_checkpoint": settings.research_durable_langgraph_checkpoint,
            "finalize_on_budget_exhausted": settings.research_finalize_on_budget_exhausted,
        },
        "model_routing": {
            "mode": "automatic",
            "default_provider": settings.llm_provider.value,
            "default_model": settings.llm_model,
        },
        "retrieval": {
            "embedding_provider": settings.resolved_embedding_provider().value,
            "embedding_model": settings.embedding_model
            or DEFAULT_EMBEDDING_MODELS.get(settings.resolved_embedding_provider(), ""),
            "embedding_dimensions": settings.embedding_dimensions,
            "mode": settings.retrieval_mode,
            "top_k": settings.retrieval_top_k,
            "candidate_k": settings.retrieval_candidate_k,
        },
        "health": {
            "api": "ok",
            "postgres": postgres,
            "vector_store": _vector_store_status(settings, postgres),
            "langsmith": "connected" if settings.langsmith_api_key is not None else "not_configured",
        },
        "security": {
            "untrusted_content": "Research titles, quotes, and reports are rendered as text.",
            "ssrf": "Private, loopback, link-local, CGNAT, and metadata URLs are blocked. Fetch pins TCP connect to the resolved IP.",
        },
    }


def _provider_status(settings: Settings) -> dict:
    return {
        "google": {"configured": settings.google_api_key is not None, "model": "gemini-3.7-flash"},
        "openai": {"configured": settings.openai_api_key is not None, "model": "gpt-4.1-mini"},
        "anthropic": {"configured": settings.anthropic_api_key is not None, "model": "claude-haiku-4-5-20251001"},
        "tavily": {"configured": settings.tavily_api_key is not None},
    }


def _langsmith_status(settings: Settings) -> dict:
    endpoint = settings.langsmith_endpoint or ""
    region = "EU" if "eu." in endpoint else ("configured" if endpoint else "unknown")
    return {
        "connected": settings.langsmith_api_key is not None and settings.langsmith_tracing,
        "project": settings.langsmith_project,
        "region": region,
        "tracing": settings.langsmith_tracing,
    }


def _vector_store_status(settings: Settings, postgres: str) -> str:
    if postgres != "ok":
        return "unavailable"
    provider = settings.resolved_embedding_provider()
    if provider not in {ProviderKind.GOOGLE, ProviderKind.OPENAI}:
        return "embedding_provider_unsupported"
    try:
        settings.require_api_key(provider)
    except ValueError:
        return "embedding_not_configured"
    return "pgvector_ready"
