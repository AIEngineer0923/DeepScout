"""Token and cost usage accounting — unknown vs zero is explicit."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from deepscout_core.domain.enums import (
    AgentRole,
    CostReportStatus,
    ResearchPhase,
    UsageReportStatus,
)


@dataclass(frozen=True, slots=True)
class TokenUsageRecord:
    """Provider-reported token usage for one model call."""

    research_run_id: UUID
    phase: ResearchPhase
    agent_role: AgentRole
    provider: str
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    task_id: UUID | None = None
    worker_id: UUID | None = None
    iteration: int | None = None
    retry: int = 0
    report_status: UsageReportStatus = UsageReportStatus.UNKNOWN

    @classmethod
    def from_provider_metadata(
        cls,
        *,
        research_run_id: UUID,
        phase: ResearchPhase,
        agent_role: AgentRole,
        provider: str,
        model: str,
        metadata: dict[str, object],
        task_id: UUID | None = None,
        worker_id: UUID | None = None,
        iteration: int | None = None,
        retry: int = 0,
    ) -> TokenUsageRecord:
        def _int(key: str) -> int | None:
            value = metadata.get(key)
            if value is None:
                return None
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        input_tokens = _int("input_tokens") or _int("prompt_token_count")
        output_tokens = _int("output_tokens") or _int("candidates_token_count")
        total = _int("total_tokens") or _int("total_token_count")
        cached = _int("cached_input_tokens") or _int("cached_content_token_count")
        reasoning = _int("reasoning_tokens") or _int("thoughts_token_count")

        known_fields = [v for v in (input_tokens, output_tokens, total) if v is not None]
        if not known_fields:
            status = UsageReportStatus.UNKNOWN
        elif input_tokens is not None and output_tokens is not None:
            status = UsageReportStatus.COMPLETE
        else:
            status = UsageReportStatus.PARTIAL

        if total is None and input_tokens is not None and output_tokens is not None:
            total = input_tokens + output_tokens

        return cls(
            research_run_id=research_run_id,
            phase=phase,
            agent_role=agent_role,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached,
            reasoning_tokens=reasoning,
            total_tokens=total,
            task_id=task_id,
            worker_id=worker_id,
            iteration=iteration,
            retry=retry,
            report_status=status,
        )


@dataclass(frozen=True, slots=True)
class RunUsageSummary:
    """Aggregated usage for a run — None means unknown, not zero."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    usage_status: UsageReportStatus = UsageReportStatus.UNKNOWN
    cost_status: CostReportStatus = CostReportStatus.UNKNOWN
    pricing_version: str | None = None


@dataclass(frozen=True, slots=True)
class ModelPricingRate:
    provider: str
    model: str
    version: str
    input_per_million_usd: float | None = None
    output_per_million_usd: float | None = None
    cached_input_per_million_usd: float | None = None
    reasoning_per_million_usd: float | None = None
    effective_from: str = ""


@dataclass
class PricingCatalog:
    """Versioned pricing table — missing entries yield UNKNOWN cost."""

    version: str
    rates: list[ModelPricingRate] = field(default_factory=list)

    def lookup(self, provider: str, model: str) -> ModelPricingRate | None:
        for rate in self.rates:
            if rate.provider == provider and rate.model == model:
                return rate
        return None

    def estimate_cost(self, usage: TokenUsageRecord) -> tuple[float | None, CostReportStatus]:
        rate = self.lookup(usage.provider, usage.model)
        if rate is None:
            return None, CostReportStatus.UNKNOWN
        if usage.input_tokens is None and usage.output_tokens is None:
            return None, CostReportStatus.UNKNOWN
        cost = 0.0
        known = False
        if usage.input_tokens is not None and rate.input_per_million_usd is not None:
            cost += usage.input_tokens * rate.input_per_million_usd / 1_000_000
            known = True
        if usage.output_tokens is not None and rate.output_per_million_usd is not None:
            cost += usage.output_tokens * rate.output_per_million_usd / 1_000_000
            known = True
        if usage.cached_input_tokens is not None and rate.cached_input_per_million_usd is not None:
            cost += usage.cached_input_tokens * rate.cached_input_per_million_usd / 1_000_000
            known = True
        if usage.reasoning_tokens is not None and rate.reasoning_per_million_usd is not None:
            cost += usage.reasoning_tokens * rate.reasoning_per_million_usd / 1_000_000
            known = True
        if not known:
            return None, CostReportStatus.UNKNOWN
        return cost, CostReportStatus.ESTIMATED
