"""Apply run-scoped research preferences to web search."""

from __future__ import annotations

from uuid import UUID

from deepscout_core.domain.research_preferences import enrich_search_query, search_provider_options
from deepscout_core.domain.schemas import SearchResult
from deepscout_persistence.store import ResearchStore

from deepscout_research.preferences.snapshot import preferences_from_snapshot
from deepscout_research.search.protocol import WebSearchProvider


def search_for_run(
    store: ResearchStore,
    run_id: UUID,
    provider: WebSearchProvider,
    query: str,
    *,
    max_results: int = 5,
    timeout_s: float = 15.0,
) -> list[SearchResult]:
    row = store.get_run_row(run_id)
    goal = row.goal if row is not None else ""
    resolved = preferences_from_snapshot(row.config_snapshot if row else None, goal=goal)
    enriched = enrich_search_query(query, resolved)
    from deepscout_research.contracts.extract import contract_from_snapshot
    from deepscout_research.contracts.source_authority import enrich_search_query_with_policy

    contract = contract_from_snapshot(row.config_snapshot if row else None)
    enriched = enrich_search_query_with_policy(enriched, contract)
    opts = search_provider_options(resolved)
    return provider.search(
        enriched,
        max_results=max_results,
        timeout_s=timeout_s,
        days=opts.get("days"),  # type: ignore[arg-type]
        topic=opts.get("topic"),  # type: ignore[arg-type]
    )


class RunScopedSearchProvider:
    """Wrap a search provider with per-run preference resolution."""

    def __init__(
        self,
        inner: WebSearchProvider,
        store: ResearchStore,
        run_id: UUID,
    ) -> None:
        self._inner = inner
        self._store = store
        self._run_id = run_id
        self.provider_name = inner.provider_name

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        timeout_s: float = 15.0,
        days: int | None = None,
        topic: str | None = None,
    ) -> list[SearchResult]:
        del days, topic
        return search_for_run(
            self._store,
            self._run_id,
            self._inner,
            query,
            max_results=max_results,
            timeout_s=timeout_s,
        )
