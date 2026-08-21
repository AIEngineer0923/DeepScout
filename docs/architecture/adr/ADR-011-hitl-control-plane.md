# ADR-011: Human-in-the-Loop control plane

Status: Accepted  
Date: 2026-08-21  
Baseline: `9b5ac368f842718e41e7aba2d8db5f3baf13de86` (resilience PASS)

## Problem

DeepScout is highly autonomous. Some boundaries require genuine human
authority (budget extension, future privileged tools, destructive knowledge
ops). Prior ADR-010 deferred product HITL; `approval.py` only blocked spoofing.

## Research (August 2026)

- **LangGraph:** `interrupt()` + `Command(resume=…)` + durable checkpointer;
  nodes re-run from the start on resume → side effects before interrupt must
  be idempotent. Official docs: LangGraph interrupts / HITL concepts.
- **LangChain:** HumanInTheLoopMiddleware (approve/edit/reject/respond) is a
  reference pattern; DeepScout keeps deterministic application policy as
  authority rather than middleware-owned permissions.
- **OpenAI Agents / Google ADK:** `needs_approval` / confirmation flows —
  comparison only; not adopted as runtime dependencies.
- **Security:** OWASP GenAI excessive agency; NIST AI RMF human oversight —
  approval is a security control, never model- or retrieval-derived.

## Decision

### Operational HITL vs human evaluation

| Domain | Purpose | Authorizes runtime? |
|---|---|---|
| Operational HITL (`review_requests`) | Pause/resume protected actions | **Yes** (api/ui/operator only) |
| Human evaluation (`human_feedback`) | Quality labels / datasets | **No** |

LangSmith annotation feedback is evaluation data only — never resolves reviews.

### Architecture

```
Policy (HumanReviewPolicy)
  → create ReviewRequest (Postgres) + payload_hash
  → ResearchRunStatus.PAUSED
  → release worker (no busy wait)
  → UI Reviews / Resume
  → approve|edit|reject|respond (authoritative source)
  → validate hash / expiry / run ownership
  → apply protected action idempotently
  → PENDING + RESUME_RUN job
```

LangGraph `interrupt()` is **documented for future privileged tool nodes**.
Budget extension uses **application-level durable pause** (PostgreSQL) —
correct for DeepScout’s deterministic orchestrator ownership.

### First concrete trigger

**BUDGET_EXTENSION** when `HITL_ENABLED` and
`HITL_BUDGET_EXTENSION_REQUIRES_REVIEW`.

Normal search/fetch/index/retrieve/extract/verify/compile remain autonomous.

### Approval binding

Canonical JSON of `proposed_action_payload` → SHA-256 `payload_hash`.
Approve/edit must match or replace via validated EDIT schema. Substitution /
TOCTOU fails closed.

### Retry ownership

Unchanged: application `RetryPolicy` only; transport `max_retries=0`.
Resume must not multiply provider attempts or duplicate cost records.

## Rejected

- Asking humans for every agent step
- Redis for HITL queues
- Second job framework / agent SDK
- Auto-approve on expiry
- Model/RAG/Wiki/LangSmith as approval sources
- Fake MODE B auth

## Future-gated

- MODE B RBAC / multi-reviewer (schema stores identity/source for extension)
- Privileged tool interrupt() nodes
- Global KB promotion reviews
- External notifications

## Accepted limitations

- MODE A single local operator
- PAUSED status = waiting-for-human (product copy)
- LangGraph interrupt not required for budget HITL v1
