"""Web search provider protocol."""

from typing import Protocol

from deepscout_core.domain.schemas import SearchResult


class WebSearchProvider(Protocol):
    provider_name: str

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        timeout_s: float = 15.0,
    ) -> list[SearchResult]: ...
