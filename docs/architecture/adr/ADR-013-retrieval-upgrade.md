# ADR-013: Retrieval architecture upgrade (August 2026)

**Status:** Accepted  
**Date:** 2026-08-22  
**Revises:** ADR-008 (extends, does not replace)

## Context

Phase 5 shipped hybrid RRF (Postgres FTS + pgvector) with deterministic rerank. That remains the backbone. Gaps identified in August 2026:

1. Postgres `ts_rank_cd` is not BM25 — identifier queries needed a true lexical scorer.
2. `plan_retrieval_query` emitted routes/corpus that `RetrievalService` ignored.
3. Contextual embeddings were not separated from evidence text.
4. `knowledge_relations` existed but was never populated.
5. Compiled LLM Wiki was post-report only, not reachable during retrieval when `corpus=compiled|both`.

SPLADE, Neo4j GraphRAG, HNSW ANN, and cross-encoder rerank were re-evaluated.

## Decisions

### Lexical: BM25 + FTS (not BM25 alone)

- **Implement true Okapi BM25** in `retrieval/bm25.py`, built in-memory per run from persisted chunks.
- **Keep Postgres FTS** as a second lexical leg in RRF (three-way fusion: BM25 + FTS + dense when `mode=hybrid`).
- Do **not** rename FTS to BM25 in documentation.

### Dense: contextual embeddings

- Chunking version `v2-contextual-1800-280`; embedding config `v2-dim768-contextual-prefix`.
- `context_text` column stores document/section prefix for embedding only; `text` remains immutable evidence.
- Re-index on new chunking/embedding spec; legacy chunks continue to work (embed `text`).

### Fusion

- RRF k=60 across all active rank lists (unchanged semantics).

### Rerank

- **Default:** deterministic (diversity, exact-token, recency) — unchanged.
- **Optional:** `RERANKER_MODE=cross_encoder` with `pip install deepscout-research[rerank]` (sentence-transformers). Not default — adds model weight and cold-start latency.

### Adaptive router

- `route_retrieval()` classifies intent (identifier, semantic, entity_relation, long_context, global_thematic).
- Scales `top_k` / `candidate_k` by research mode (quick/standard/deep).
- Persists decision in `RetrievedChunk.strategy_trace` and LangSmith retriever spans.

### Graph retrieval (local, not GraphRAG communities)

- Populate `knowledge_relations` during wiki compile (same-source statement links).
- `graph_search_statements()` — entity token match + bounded 1-hop walk.
- **Rejected:** community detection, global summaries, Neo4j — no measured gain on run-scoped corpora.

### LLMWiki in retrieval

- When `corpus=compiled|both`, merge `query_compiled_statements` hits (provenance_kind=compiled).
- Compiled hits never replace chunk evidence in EXTRACT — `assemble_context` filters to `provenance_kind=chunk` for quote resolution.

### SPLADE / learned sparse

- **Rejected** for production. Run-scoped corpora are small; BM25 + dense + FTS covers identifier and semantic cases without GPU sparse index ops.

### Long-context

- Unchanged policy: snapshots ≤1000 estimated tokens skip vector retrieval; full snapshot used in EXTRACT.

### ANN indexes

- **Deferred** — exact pgvector scan remains default (ADR-008).

## Migration

- `013_contextual_chunks.py` — nullable `document_chunks.context_text`
- `/ready` expects Alembic head `013`

## Consequences

- New runs re-index with contextual chunks when embedding keys are configured.
- Legacy runs without `context_text` continue to retrieve using chunk `text`.
- Ablation: `scripts/retrieval_ablation_offline.py` (BM25 offline); live ablation remains `scripts/phase5_closure_gate.py`.
- Quality suite v2: `scripts/retrieval_quality_benchmark.py` + `libs/evaluation/data/retrieval_quality_benchmark_v2.json` — router confusion matrix, per-retriever ablation, contextual raw vs prefix comparison, compiled + local graph fixtures.
