# ADR-010: Production model routing, resilience, and runtime hardening

Status: Accepted  
Date: 2026-08-21

## Context

DeepScout already has a multi-provider LangChain factory, a role-based `ModelRouter`,
central `retry.py`, Postgres-backed jobs/checkpoints, LangSmith (default-off), and
MODE A local/trusted-network deployment. Phase 5 retrieval and the compiled knowledge
layer are complete on main.

A production-agent gap review asked whether to adopt LiteLLM, Redis application
services, Langfuse, OpenTelemetry, distributed circuit breakers, cloud orchestrators,
and product human-in-the-loop — without cargo-culting a generic AI stack diagram.

## Decision summary

| Topic | Decision |
|---|---|
| Internal ModelRouter + capability registry | **ADOPT_NOW** (extend existing) |
| LiteLLM SDK | **REJECT** (MODE A) |
| LiteLLM Proxy | **REJECT** (MODE A) |
| Redis application use | **REJECT** / probe-only (**FUTURE_GATED** for multi-instance) |
| LangSmith | **KEEP primary** |
| Langfuse | **REJECT** (duplicate tracing) |
| OpenTelemetry | **DEFER** |
| Circuit breaker | **IMPLEMENT** in-process provider health only |
| Chat fallback | **OPTIONAL** capability + privacy + budget-gated via policy |
| Embedding fallback across spaces | **REJECT** (never silent mix) |
| Human-in-the-loop product pause | **DEFER** (security primitives only) |
| AWS/GCP/K8s | **REJECT** for now (container-portable MODE A) |

## Current model architecture

```
Settings (LLM_PROVIDER / LLM_MODEL / timeouts)
  → ModelRouter.resolve(role [, requirements])
  → capability + privacy filter
  → optional ProviderHealthRegistry
  → build_chat_model / options_from_settings
  → LangChain provider adapter
```

Application retry ownership: `deepscout_research.retry.run_with_retry` and
`routing.resilient_invoke.invoke_with_resilience` are the **sole** logical retry
authorities. LangChain `max_retries` is fixed at `PROVIDER_TRANSPORT_MAX_RETRIES=0`
via `options_from_settings` — never mirrored from `LLM_MAX_RETRIES`.

## LiteLLM evaluation

**SDK:** Would normalize provider APIs DeepScout already wraps via LangChain. Adds
dependency surface, another retry layer, and weaker typed capability guarantees.
**Proxy:** Central credential/routing gateway helps multi-team orgs; MODE A is a
single local process with keys in env — proxy adds attack surface and ops cost without
a measured need.

## Redis evaluation

Jobs, leases, and LangGraph checkpoints are PostgreSQL. Redis exists in Compose for
optional probe only (`redis_required=False`). No cache/queue/lock requirement justified
for MODE A.

## Human-in-the-loop

LangGraph `interrupt()` + durable checkpointer is the correct *mechanism* when HITL
is productized. DeepScout does **not** pause normal research for humans. Escalation
candidates (privileged tools, global knowledge promotion, destructive wiki ops) remain
future. `approval.py` ensures model/retrieved text cannot spoof approval.

## Retry ownership (single model)

1. **Application `RetryPolicy` / `run_with_retry` / `invoke_with_resilience`
   own all logical retries** for model and search invocations.
2. **`LLM_MAX_RETRIES`** sets application `max_attempts` only
   (`application_retry_policy`).
3. **LangChain/provider transport `max_retries` is always
   `PROVIDER_TRANSPORT_MAX_RETRIES` (0)** — Google treats 0/1 as no retries;
   OpenAI/Anthropic honor 0. This prevents nested amplification
   (`app_attempts × provider_retries`).
4. Job/task reclaim owns domain redelivery — not LLM HTTP retries.
5. Never retry security/policy/cancel/budget permanent failures.
6. Do not stack unbounded orchestrator retries on top.

**Max effective provider requests** (transport retries disabled):

- no fallback: `LLM_MAX_RETRIES`
- fallback allowed: `LLM_MAX_RETRIES × 2` (primary then fallback)

Failed attempts do not invent `cost=0`; usage is recorded only after a successful
response with provider metadata (otherwise UNKNOWN).

## Fallback policy

Fallback only when:

- explicitly configured on `AgentModelPolicy`;
- `ModelRequirements.fallback_allowed`;
- fallback satisfies capabilities;
- fallback provider ∈ privacy allowlist;
- provider health permits;
- error class is fallback-eligible.

Embeddings: never cross-space fallback.

## Health semantics

| Endpoint | Meaning |
|---|---|
| `/health`, `/live` | Process liveness |
| `/ready` | Postgres authoritative readiness (503 if down) |
| `/api/v1/health/deps` | Postgres + Redis probe; Redis not required |

LangSmith outage must not fail readiness.

## Graceful shutdown

API lifespan disposes SQLAlchemy pooled engines via `dispose_all_engines()`.

## Consequences

- Capability-aware routing without a gateway.
- Measured resilience tests without new infrastructure.
- HITL remains honest (deferred), not fake UI.
- Future multi-instance may reconsider Redis/LiteLLM Proxy with new evidence.
