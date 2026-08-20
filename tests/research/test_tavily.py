from unittest.mock import MagicMock, patch

import httpx
import pytest
from deepscout_core.domain.schemas import SearchResult
from deepscout_core.settings import Settings
from deepscout_research.search.tavily import TavilyWebSearchProvider


def test_tavily_normalizes_results() -> None:
    settings = Settings(_env_file=None, TAVILY_API_KEY="test-key")
    response = MagicMock()
    response.raise_for_status = MagicMock()
    response.json.return_value = {
        "results": [
            {
                "url": "https://example.com/a",
                "title": "Example",
                "content": "snippet text",
                "score": 0.91,
            }
        ]
    }
    with patch.object(httpx.Client, "post", return_value=response):
        with TavilyWebSearchProvider(settings) as provider:
            results = provider.search("battery tech", max_results=3)
    assert results == [
        SearchResult(
            url="https://example.com/a",
            title="Example",
            snippet="snippet text",
            score=0.91,
        )
    ]


def test_tavily_requires_api_key() -> None:
    settings = Settings(_env_file=None, TAVILY_API_KEY=None)
    with pytest.raises(ValueError, match="TAVILY_API_KEY"):
        TavilyWebSearchProvider(settings)
