# RAG Pipeline (Phase 5)

## Provenance chain

```text
Source → immutable SourceSnapshot → DocumentChunk (derived) → ChunkEmbedding (derived)
Evidence → quote resolved in SourceSnapshot.text (never embedding row)
```

## Indexing flow

1. Fetch creates `SourceSnapshot`
2. `index_snapshots_for_run` chunks text (`v1-recursive-1800-280`)
3. Batch embeddings (Google `gemini-embedding-2` default **768** dims; OpenAI `text-embedding-3-small` may use 1536)
4. Persist vectors in `chunk_embeddings` with provider/model/dimensions/config_version
5. Snapshot `indexing_status` → `indexed` | `failed` | `skipped`

Backfill: `uv run python scripts/deepscout_index.py <run_id>`

## Retrieval flow

1. `plan_retrieval_query` → structured `QueryPlan`
2. `RetrievalService.retrieve` → lexical + dense (hybrid default)
3. Reciprocal Rank Fusion (k=60)
4. Deterministic rerank (source diversity, recency, exact-token boost)
5. Optional bounded re-retrieval (widen `candidate_k` once if grader insufficient)
6. Extract uses retrieved passages as **search hints**; evidence quotes still located in full snapshot

## Isolation

Every SQL query filters `research_run_id`. No cross-run retrieval.

## Configuration

See `.env.example`: `EMBEDDING_*`, `RETRIEVAL_MODE`, `RETRIEVAL_TOP_K`, `RETRIEVAL_CANDIDATE_K`.

See ADR-008 and `RAG_TECHNIQUE_LANDSCAPE.md` for technique decisions.
