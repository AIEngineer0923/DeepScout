"""Capability-aware discovery router with provider fallback and deduplication."""

from __future__ import annotations

from dataclasses import dataclass

from deepscout_core.domain.contracts import SourceKind
from deepscout_core.domain.schemas import SearchResult
from deepscout_core.settings import Settings

from deepscout_research.fetch.url_normalize import normalize_source_url
from deepscout_research.search.protocol import WebSearchProvider
from deepscout_research.source_fabric.providers import (
    DiscoveryProvider,
    GitHubDiscoveryProvider,
    OpenAlexDiscoveryProvider,
)
from deepscout_research.source_fabric.registry import (
    ConnectorRegistry,
    baseline_connector_registry,
)
from deepscout_research.source_fabric.strategy import (
    DiscoveryRequest,
    QueryStrategy,
    evidence_role_for_kind,
    infer_source_kind,
)


@dataclass(frozen=True, slots=True)
class DiscoveryAttempt:
    provider: str
    success: bool
    result_count: int
    error: str = ""


class IndexedWebDiscoveryProvider:
    def __init__(self, inner: WebSearchProvider, registry: ConnectorRegistry) -> None:
        self._inner = inner
        self.provider_name = inner.provider_name
        capability = registry.get("indexed_web")
        if capability is None:
            raise RuntimeError("indexed_web capability is not registered")
        self.capability = capability

    def discover(self, request: DiscoveryRequest) -> list[SearchResult]:
        results = self._inner.search(
            request.query,
            max_results=request.max_results,
            days=request.freshness_days,
            topic=request.topic,
        )
        output: list[SearchResult] = []
        for item in results:
            kind = infer_source_kind(item.url, title=item.title)
            output.append(
                item.model_copy(
                    update={
                        "discovery_provider": item.discovery_provider or self.provider_name,
                        "source_kind": kind.value,
                        "query_strategy": request.strategy.value,
                        "evidence_role": evidence_role_for_kind(kind),
                    }
                )
            )
        return output

    def close(self) -> None:
        close = getattr(self._inner, "close", None)
        if close:
            close()


class DiscoveryRouter:
    provider_name = "source_discovery_router"

    def __init__(
        self,
        providers: list[DiscoveryProvider],
        registry: ConnectorRegistry,
    ) -> None:
        self._providers = providers
        self.registry = registry
        self.last_attempts: tuple[DiscoveryAttempt, ...] = ()

    def _eligible(self, provider: DiscoveryProvider, request: DiscoveryRequest) -> bool:
        if not request.source_kinds:
            return provider.capability.connector_id == "indexed_web"
        return bool(provider.capability.source_kinds & request.source_kinds)

    def discover(self, request: DiscoveryRequest) -> list[SearchResult]:
        attempts: list[DiscoveryAttempt] = []
        merged: list[SearchResult] = []
        for provider in self._providers:
            if not self._eligible(provider, request):
                continue
            try:
                results = provider.discover(request)
                attempts.append(DiscoveryAttempt(provider.provider_name, True, len(results)))
                merged.extend(results)
            except Exception as exc:
                attempts.append(
                    DiscoveryAttempt(provider.provider_name, False, 0, type(exc).__name__)
                )
                continue
        self.last_attempts = tuple(attempts)
        deduped: list[SearchResult] = []
        seen: set[str] = set()
        for item in sorted(merged, key=lambda value: value.score or 0.0, reverse=True):
            try:
                key = normalize_source_url(item.url)
            except ValueError:
                key = item.url
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= request.max_results:
                break
        return deduped

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        timeout_s: float = 15.0,
        days: int | None = None,
        topic: str | None = None,
    ) -> list[SearchResult]:
        del timeout_s
        return self.discover(
            DiscoveryRequest(
                query=query,
                max_results=max_results,
                strategy=QueryStrategy.GENERAL,
                source_kinds=frozenset({SourceKind.WEB_PAGE}),
                freshness_days=days,
                topic=topic,
            )
        )

    def close(self) -> None:
        for provider in self._providers:
            provider.close()

    def __enter__(self) -> DiscoveryRouter:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def build_discovery_router(
    settings: Settings,
    web_provider: WebSearchProvider,
) -> DiscoveryRouter:
    del settings  # Structured public connectors need no secret in the baseline.
    registry = baseline_connector_registry()
    providers: list[DiscoveryProvider] = [IndexedWebDiscoveryProvider(web_provider, registry)]
    openalex = registry.get("openalex")
    github = registry.get("github_public_api")
    if openalex is not None:
        providers.append(OpenAlexDiscoveryProvider(openalex))
    if github is not None:
        providers.append(GitHubDiscoveryProvider(github))
    return DiscoveryRouter(providers, registry)
