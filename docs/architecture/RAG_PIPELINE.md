# RAG Pipeline

Internal retrieval for **uploaded documents** and **stored snapshots** — distinct from web search.

## Pipeline

```text
Document / Snapshot text
  → Loader (MIME-aware)
  → Splitter (chunk + overlap)
  → Embeddings (provider factory)
  → pgvector store
  → Retriever (similarity + filters)
  → Claim extraction agent (with citations)
```

## Components (Phase 4+)

| Step | Location | LangChain |
|---|---|---|
| Load | `libs/retrieval/loaders/` | Document loaders |
| Split | `libs/retrieval/splitters/` | `RecursiveCharacterTextSplitter` |
| Embed | `libs/providers/` | Provider embeddings |
| Store | `libs/retrieval/vectorstores/` | pgvector adapter |
| Retrieve | `libs/retrieval/` | retriever interface |

## vs web research

| | Web search | RAG |
|---|---|---|
| Input | Live web | Stored snapshots/uploads |
| Tool | `WebSearchProvider` | `semantic_retrieve` |
| Output | `Source` + `SourceSnapshot` | Chunks → `Claim` + `Evidence` |

## Security

All loaded content passes through sanitization before prompt inclusion.
See [SECURE_FETCH_PIPELINE.md](SECURE_FETCH_PIPELINE.md).
