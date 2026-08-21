# Provider Architecture

## LLM providers

Supported first-class providers:

| Provider | Package | Factory branch |
|---|---|---|
| Google | `langchain-google-genai` | `ChatGoogleGenerativeAI`, `GoogleGenerativeAIEmbeddings` |
| OpenAI | `langchain-openai` | `ChatOpenAI`, OpenAI embeddings |
| Anthropic | `langchain-anthropic` | `ChatAnthropic` |

## Configuration

```bash
LLM_PROVIDER=google|openai|anthropic
LLM_MODEL=<model-id>
EMBEDDING_PROVIDER=google|openai|anthropic
EMBEDDING_MODEL=<model-id>
```

## Factory pattern

```text
apps/api, libs/research, libs/retrieval
        │
        ▼
  build_llm_provider(settings)   ← only entry point
        │
        ├── GoogleLLMProvider
        ├── OpenAIProvider
        └── AnthropicProvider
```

**Rule:** no provider imports outside `libs/providers/`.

## Model defaults

Centralized in `libs/providers/defaults.py` (Phase 1).

Model IDs must be verified against **current official docs** before implementation:

- LangChain integration docs
- Google AI / Gemini model list
- OpenAI models API docs
- Anthropic models docs

Never hardcode model IDs in research/domain code.

## Web search (separate from LLM)

```python
class WebSearchProvider(Protocol):
    async def search(self, query: str, *, max_results: int) -> list[SearchResult]: ...


class TavilySearchAdapter(WebSearchProvider): ...


# Future: BraveSearchAdapter, SerpAPIAdapter, MCPSearchAdapter
```

Research workflow depends on `WebSearchProvider`, not Tavily.
