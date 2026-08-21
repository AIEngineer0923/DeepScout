# RAG Technique Landscape Review (August 2026)

Baseline: `d18e91bec0fa5fee90a64836e36d5d039c78c5cd`

Verdict legend:

- **IMPLEMENT** — in Phase 5 production path
- **DEFER** — not needed now; revisit with data
- **EVALUATED_AND_DEFERRED** — reviewed; rejected for current scope
- **FUTURE_MODALITY_GATED** — architecture only

## Query understanding

| Technique | Verdict | DeepScout note |
|---|---|---|
| Query normalization | IMPLEMENT | `RetrievalQuery` strips/limits query text |
| Query classification | DEFER | Research planner already decomposes tasks |
| Intent detection | DEFER | Extraction uses candidate query + snippet |
| Query rewriting | EVALUATED_AND_DEFERRED | Extra LLM call; no measured gain yet |
| Query expansion | EVALUATED_AND_DEFERRED | Risk of semantic drift / cost |
| Multi-query retrieval | EVALUATED_AND_DEFERRED | Policy OFF; adaptive later |
| Query decomposition | DEFER | Global = Planner DAG; local only if one task has multiple intents |
| Step-back / HyDE | EVALUATED_AND_DEFERRED | Not justified on small corpora |
| Entity extraction | IMPLEMENT (light) | CVE/version patterns in `plan_retrieval_query` |
| Temporal intent | IMPLEMENT (metadata) | `fresher_than` filter + recency rerank |
| Metadata filter inference | IMPLEMENT | `run_id`, `source_ids` required |

## Routing

| Technique | Verdict | DeepScout note |
|---|---|---|
| Semantic / retrieval routing | IMPLEMENT | `RetrievalStrategy` + settings |
| Poly-retriever routing | IMPLEMENT (limited) | Hybrid lexical + dense only |
| SQL vs vector vs graph | IMPLEMENT | SQL/repositories for structured state; vector for passages; PostgreSQL evidence graph |
| Web routing | IMPLEMENT (existing) | Tavily fetch remains separate from index retrieval |
| Dedicated graph DB | EVALUATED_AND_DEFERRED | PostgreSQL joins sufficient |

## Retrieval / fusion / rerank

| Technique | Verdict | DeepScout note |
|---|---|---|
| Dense pgvector | IMPLEMENT | Exact cosine scan, run-scoped |
| PostgreSQL FTS | IMPLEMENT | `simple` config for exact tokens |
| Hybrid + RRF | IMPLEMENT | k=60 |
| Cross-encoder rerank | EVALUATED_AND_DEFERRED | Deterministic rerank sufficient for v1 |
| LLM rerank | EVALUATED_AND_DEFERRED | Cost/injection risk |
| ColBERT / late interaction | EVALUATED_AND_DEFERRED | Ops/index size vs small corpora |
| HNSW / IVFFlat | EVALUATED_AND_DEFERRED | Exact scan for local corpora |

## Indexing / representation

| Technique | Verdict | DeepScout note |
|---|---|---|
| Heading-aware chunking | IMPLEMENT | `v1-recursive-1800-280` |
| Semantic splitting | EVALUATED_AND_DEFERRED | Needs controlled experiment |
| Hierarchical indexes | EVALUATED_AND_DEFERRED | Flat chunks + section metadata first |
| Multi-representation | DEFER | Single chunk text + FTS generated column |
| Parent/child chunks | DEFER | Offsets link to snapshot |

## Generation / control

| Technique | Verdict | DeepScout note |
|---|---|---|
| Agentic RAG loops | EVALUATED_AND_DEFERRED | Bounded re-retrieval only (widen candidate_k once) |
| CRAG / Self-RAG | EVALUATED_AND_DEFERRED | Ideas folded into grader + existing verify/critic |
| Active retrieval policy | IMPLEMENT (partial) | Skip retrieval for small snapshots |
| Long-context vs RAG | IMPLEMENT | ≤1000 token docs use full snapshot in extract |

## Memory / eval / security

| Technique | Verdict | DeepScout note |
|---|---|---|
| Global shared memory | EVALUATED_AND_DEFERRED | Run-scoped only |
| RAGAS | IMPLEMENT (optional layer) | `ragas_eval.py`; offline when installed |
| Redis retrieval cache | EVALUATED_AND_DEFERRED | No measured benefit yet |
| Multimodal RAG | FUTURE_MODALITY_GATED | Not in product |
| Code retrieval | FUTURE_MODALITY_GATED | Separate future feature |

## Production default

**Hybrid lexical + dense → RRF → deterministic rerank → grader → context assembly**

Evidence still resolves against immutable `SourceSnapshot` text, never chunk rows alone.
