# Graphify evaluation (Gate B)

**Date:** 2026-08-21  
**Scope:** DeepScout runtime vs private coding-agent workflow  
**Sources consulted:** [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify), [graphify.com/docs](https://graphify.com/docs), Karpathy [LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)

## What Graphify is

Graphify is a **codebase / multimodal coding-assistant skill**: tree-sitter AST parsing for code (local, deterministic), optional LLM semantic extraction for docs/media, NetworkX graph + MCP tools (`query_graph`, `shortest_path`, etc.). It is **not** a research-evidence graph over web snapshots, claims, and citations.

## DeepScout runtime decision

**GRAPHIFY_DEEPSCOUT_RUNTIME = REJECT**

| Criterion | Assessment |
|---|---|
| Capability overlap | DeepScout already has PostgreSQL evidence graph (Source → Snapshot → Evidence → Claim → Contradiction) + hybrid RAG |
| Domain fit | Graphify targets code/docs AST navigation; DeepScout targets run-scoped research provenance |
| Security / ops | Extra graph artifact + MCP surface without authority model for research evidence |
| Licensing | Permissive (Apache/MIT variants across forks) — not the blocker |
| Maintenance | Another graph projection to keep consistent with Postgres truth |

Do **not** install Graphify into the DeepScout application, Docker image, or CI.

## Private Master Agent OS / coding workflow

**GRAPHIFY_MASTER_AGENT_OS = DEFER**

Separately from this repository, Graphify may help coding agents with:

1. architecture reconstruction  
2. symbol / call-graph navigation  
3. multi-hop dependency tracing  
4. blast-radius analysis  
5. frontend → API → DB path tracing  

Evaluation must stay **outside** the public DeepScout tree. Do not commit private agent prompts, skills, rules, or local Master Agent OS paths.

Recommended private experiment checklist (outside repo): install `graphifyy[mcp]` in an isolated tool env; index a coding workspace only; compare against existing search/Serena/ripgrep for the ten coding tasks listed in Gate B §B31; adopt only if multi-hop navigation measurably improves without leaking private content.

## Relationship to LLM Wiki

Karpathy’s LLM Wiki pattern compiles **persistent markdown knowledge** between raw sources and queries. DeepScout adapts that idea as a **run-scoped, provenance-linked Wiki** derived from Claims/Evidence — never as a replacement for hybrid RAG or as a Graphify dependency.
