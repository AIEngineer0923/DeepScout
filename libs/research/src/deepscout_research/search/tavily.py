"""Tavily web search adapter."""

from __future__ import annotations

import httpx
from deepscout_core.domain.schemas import SearchResult
from deepscout_core.settings import Settings


class TavilyWebSearchProvider:
    provider_name = "tavily"

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.require_tavily_api_key()
        self._client = httpx.Client(timeout=20.0)

    def search(
        self,
        query: str,
        *,
        max_results: int = 5,
        timeout_s: float = 15.0,
    ) -> list[SearchResult]:
        response = self._client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self._api_key,
                "query": query,
                "max_results": max_results,
                "include_answer": False,
            },
            timeout=timeout_s,
        )
        response.raise_for_status()
        payload = response.json()
        results: list[SearchResult] = []
        for item in payload.get("results", [])[:max_results]:
            results.append(
                SearchResult(
                    url=str(item.get("url", "")),
                    title=str(item.get("title", "")),
                    snippet=str(item.get("content", ""))[:8000],
                    score=float(item["score"]) if item.get("score") is not None else None,
                )
            )
        return [result for result in results if result.url]

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> TavilyWebSearchProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
