# ADR-008: Hybrid snapshot retrieval with exact pgvector search

**Status:** Accepted (Phase 5)
**Date:** 2026-08-21
**Baseline:** `d18e91bec0fa5fee90a64836e36d5d039c78c5cd`

## Context

DeepScout already persists immutable `SourceSnapshot` rows. Extraction scans whole snapshots with keyword overlap. That misses paraphrase and does not scale to long documents. Phase 5 must add retrieval without creating a second source of truth, mixing embedding spaces, or leaking chunks across runs.

Official docs consulted at implementation time:

- Gemini embeddings: `gemini-embedding-2` is the current recommended model; output dimensions 128–3072 (recommended 768 / 1536 / 3072); 8192 input tokens; `task_type` is **not** supported on this model (use an instruction prefix instead).
- OpenAI: `text-embedding-3-small` remains the cheap portable dense model (1536 dims).
- Anthropic: no first-party embedding API — do not fake parity.
- pgvector: cosine distance `<=>`; HNSW/IVFFlat are approximate indexes. IVFFlat cosine is capped at 2000 dimensions. Exact `ORDER BY embedding <=> query` is correct for small local corpora.
- LangChain: hybrid retrieval is commonly fused with Reciprocal Rank Fusion (RRF), not by adding raw scores.

## Options

| | Recall of paraphrase | Exact IDs / CVEs / quotes | Cost | Ops | Confirmation-bias risk |
|---|---|---|---|---|---|
| A. Dense-only pgvector | High | Weak | Embedding spend | Low | High if used as “truth” |
| B. Lexical-only Postgres FTS | Weak | High (`simple` config) | None after index | Lowest | Medium |
| C. Hybrid RRF (dense + lexical) | High | High | Embedding spend | Moderate | Medium |
| D. C + paid/LLM rerank | Slightly higher | High | Extra model calls | Higher | Reranker injection |

## Decision

**Production default: C + deterministic post-fusion rerank (not a second LLM).**

1. **Chunks are derived** from `SourceSnapshot` only. Tavily snippets never become chunks.
2. **Dense retriever:** pgvector cosine, **exact scan** (no HNSW/IVFFlat). Local corpora are small; HNSW on tens of vectors adds operational cost without recall benefit. Upgrade path: add `USING hnsw (embedding vector_cosine_ops)` later when measured latency requires it. Default stored dimension **768** for Google `gemini-embedding-2` after a symmetric 768-vs-1536 benchmark showed identical Hit@K / Recall@K / MRR / NDCG / phrase-recall on `retrieval-benchmark-v1.1` with half the vector storage. OpenAI `text-embedding-3-small` may still use 1536. Spaces never mix: queries filter `provider + model + dimensions + config_version`.
3. **Lexical retriever:** `to_tsvector('simple', text)` + `plainto_tsquery('simple', query)` so CVE IDs, versions, and acronyms are not stemmed away.
4. **Fusion:** Reciprocal Rank Fusion with `k=60`. Ranks are comparable; raw cosine and ts_rank are not.
5. **Rerank:** deterministic only — source diversity (max 3 chunks per source), recency (`retrieved_at`), exact-token boost. No cross-encoder or LLM reranker until a retrieval dataset shows material NDCG gain.
6. **Query rewrite / multi-query:** deferred. Extra LLM calls without measured recall gain; original query is always the retrieval key.
7. **Indexing:** deterministic job after fetch, not an LLM agent. Idempotent on `(snapshot_id, chunking_version, embedding spec)`.
8. **Isolation:** every query requires `research_run_id`. No global memory.

## Structured retrieval planner (§78)

`plan_retrieval_query` emits a typed `QueryPlan` (lexical/semantic query, entities, filters, routes, top_k). It does **not** decide factual truth. Small snapshots (≤1000 estimated tokens) skip retrieval and use full snapshot text (long-context policy §94).

## Technique landscape

See `docs/architecture/RAG_TECHNIQUE_LANDSCAPE.md` for August 2026 review verdicts (IMPLEMENT / DEFER / EVALUATED_AND_DEFERRED). Production path is hybrid RRF + deterministic rerank — not 2023-style top-5 cosine stuffing.

## Poly-routing decision (§79–81)

| Question type | Route |
|---|---|
| Claims/evidence counts, contradictions, provenance | PostgreSQL repositories (typed queries) |
| Passage lookup in fetched corpus | Hybrid lexical + pgvector |
| Fresh public evidence | Web search + fetch (existing) |
| Multi-hop entity graph | PostgreSQL relational graph — no Neo4j |

## Evaluation layers (§106)

- DeepScout deterministic evaluators (primary)
- LangSmith experiments/traces (operational)
- RAGAS optional offline wrapper when labeled ground truth exists

## Consequences

- Application embedding spend is recorded as usage (UNKNOWN cost if the catalog has no rate).
- Contributors must configure Google or OpenAI embeddings; Anthropic chat still works with a separate embedding provider.
- Existing snapshots are **not** embedded by Alembic; `deepscout-index` backfills at runtime.

## August 2026 research decisions (master gate)

### LLM Wiki

**Decision: IMPLEMENTED_OPTIONAL — see ADR-009.**

Karpathy's LLM Wiki compiles navigable knowledge from sources. DeepScout implements a **run-scoped, provenance-linked** Wiki derived from Claims/Evidence. It does **not** replace hybrid RAG and is never treated as evidence.

### Obsidian

**Decision: OPTIONAL_EXPORT (future) — NOT_NEEDED at runtime.**

Obsidian wikilinks/backlinks are useful for human inspection of exported Markdown vaults. DeepScout must not depend on a desktop app. Optional export path: Wiki/Markdown + frontmatter + `[[wikilinks]]`.

### Graphify

**Decision: REJECTED for DeepScout runtime; OPTIONAL for private coding-agent workflows.**

Graphify targets code AST graphs and dev-agent navigation — not general research evidence over web snapshots. DeepScout's evidence graph (Source/Snapshot/Claim/Evidence/Contradiction) is served by PostgreSQL joins. No dedicated graph DB.

### ColBERT / late interaction

**Decision: EVALUATED_AND_DEFERRED.** Small local corpora; exact hybrid sufficient on benchmark v1 (hybrid phrase-recall 0.833 vs lexical 0.5).

### Multi-query / decomposition

**Decision: OFF (adaptive policy deferred).** Bounded multi-query did not beat single hybrid on benchmark v1; extra cost/latency unjustified.

### Semantic chunking

**Decision: EVALUATED_AND_DEFERRED.** `v1-recursive-1800-280` structural chunking performs adequately; semantic splitting adds ingestion cost/nondeterminism.

### RAGAS

**Decision: EVALUATED_AND_DEFERRED.** Thin optional wrapper (`ragas_eval.py`); DeepScout deterministic metrics + LangSmith cover primary gates. Install RAGAS only when labeled ground-truth datasets require its specific judges.

### Adaptive / Self-RAG / CRAG

**Decision: Partial adoption via existing grader + bounded re-retrieval + verify/critic.** No parallel Self-RAG framework.

## Measured results (closure gate 2026-08-21)

| Check | Result |
|---|---|
| Google embedding runtime model | `gemini-embedding-2` |
| Default dimensions | **768** (1536 equivalent on shared metrics; 2× storage) |
| Indexing (4 docs) | PASS, both dimension spaces |
| Cross-run isolation | PASS (0 hits) |
| Ablation Hit@K | FTS 0.583, dense 0.917, hybrid RRF 0.917, hybrid+rerank 0.917 |
| Category robustness | LEXICAL_IDENTIFIER all modes strong; SEMANTIC favors dense/hybrid over FTS |
| Reranker quality delta | 0.0 on this corpus (retained as policy: diversity / exact-token / retrieved_at) |
| Isolated pre-RAG vs RAG | SIMILAR (2 claims / 2 evidence each; separate runs) |
| Dimension decision | **768 default** — material quality equivalence; lower storage |

LangSmith: dataset `deepscout-retrieval-v1`, experiments `deepscout-retrieval-YYYYMMDD-dim768|dim1536|ablation-*` (EU workspace).

Do **not** claim hybrid universally beats dense. Hybrid is the default for **category robustness** (lexical identifiers + semantic paraphrase) with RRF rank fusion.

## Authority model

PostgreSQL domain/evidence = authority. Chunks/embeddings/indexes = derived rebuildable artifacts. Retrieval = candidate generation, not verification.

