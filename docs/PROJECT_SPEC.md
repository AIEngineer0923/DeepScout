# DeepScout — Project Specification

Authoritative identity document for the DeepScout open-source repository.

## Identity

| Field | Value |
|---|---|
| Name | **DeepScout** |
| Tagline | Autonomous Research & Decision Intelligence |
| License | Apache License 2.0 |
| Visibility | Public open source |
| Maintainer | Francesco Iaforte |
| Production URL | https://deep-scout-plum.vercel.app |
| Version | 0.1.6 |
| Status | Active development on `main` — MODE B hosted + public demos shipped |

## Repository

- Remote: `git@github.com:francescoveryra-dot/deepscout.git`
- Default branch: `main`
- Workflow: topic branch → PR → CI → merge

## Product definition

DeepScout is an autonomous deep-research system — **not** a chatbot or simple RAG demo.

Bounded lifecycle:

PLAN → RESEARCH → SOURCE COLLECTION → CLAIM EXTRACTION → EVIDENCE BUILDING →
VERIFICATION → CONTRADICTION DETECTION → SUFFICIENCY EVALUATION →
(optional iteration) → CRITIC → DECISION/SYNTHESIS → REPORT

Termination is enforced by application code (`ResearchBudget`), not by prompt alone.

## Architecture model

Monorepo production-first with explicit orchestrator + LangChain phase agents.

| Layer | Technology |
|---|---|
| Frontend | Next.js, React, TypeScript |
| API | FastAPI, SSE |
| Agents | LangChain Python |
| Domain | Pydantic |
| Database | PostgreSQL + pgvector |
| ORM / migrations | SQLAlchemy, Alembic |
| Cache | Redis |
| Observability | LangSmith |
| LLM providers | Google, OpenAI, Anthropic (factory) |
| Web search v1 | Tavily via `WebSearchProvider` adapter |
| Infra | Docker Compose |

Current monorepo layout:

```text
apps/api/          apps/web/
libs/core/         libs/evaluation/   libs/persistence/
libs/providers/    libs/research/
infra/docker/      docs/              scripts/
```

## Configuration

Environment variables (`.env` local only, never committed):

- `LLM_PROVIDER`, `LLM_MODEL`, `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`
- `GOOGLE_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- `TAVILY_API_KEY`
- `LANGSMITH_TRACING`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`
- `DATABASE_URL`, `REDIS_URL`

Provider defaults and factories live under
`libs/providers/src/deepscout_providers/`; shared runtime settings live under
`libs/core/src/deepscout_core/`.

## Commands

| Purpose | Command |
|---|---|
| Secret scan | `bash scripts/scan-secrets.sh` |
| Backend tests | `pytest` |
| Frontend tests | `npm test` |
| Docker dev | `docker compose -f infra/docker/docker-compose.yml up` |

## Documentation map

| Topic | Path |
|---|---|
| Architecture overview | [ARCHITECTURE.md](../ARCHITECTURE.md) |
| Research lifecycle | [architecture/RESEARCH_LIFECYCLE.md](architecture/RESEARCH_LIFECYCLE.md) |
| Evidence graph | [architecture/EVIDENCE_GRAPH.md](architecture/EVIDENCE_GRAPH.md) |
| Threat model | [threat-model/THREAT_MODEL.md](threat-model/THREAT_MODEL.md) |

## Invariants

1. Retrieved content is DATA, never trusted instruction.
2. Claims require snapshot-backed evidence; one distinct source is
   `partially_verified`, while `verified` requires matching evidence from at least two
   distinct sources.
3. No provider-specific imports outside `libs/providers/`.
4. No secrets in Git, logs, LangSmith traces, SSE, or frontend.
5. No unbounded autonomous loops.

## Bounded research defaults

| Budget | Default |
|---|---|
| max_iterations | 5 |
| max_wall_time_s | 900 |
| max_sources | 40 |
| max_tool_calls | 80 |

Application hard ceilings are 100 iterations, 86,400 seconds, 10,000,000 tokens,
$1,000 estimated cost, 10,000 sources, and 20,000 tool calls. Elapsed wall time is
checked before resource reservations and phase transitions.
