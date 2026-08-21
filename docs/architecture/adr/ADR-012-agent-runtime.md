# ADR-012: Agent runtime and intelligence layer

Status: Accepted  
Date: 2026-08-21  
Baseline: `35cc1a589cb6ce7c9d261691e8c4f3788ffa4be1` (HITL PASS)

## Problem

DeepScout already has a deterministic orchestrator, DAG workers, RAG, Wiki,
resilience, and HITL. It did not yet have a first-class agent-runtime policy
for context budgets, skills, adaptive allocation, bounded replanning, or
safe fork/replay.

## Research (August 2026)

- **Anthropic Agent Skills** (`agentskills.io`): SKILL.md + progressive
  disclosure (metadata → body → resources). Skills are procedure, not
  permission. DeepScout adopts the open file format; **application SkillRouter
  selects skills**. `allowed-tools` in a skill cannot grant tools.
- **Building Effective Agents / multi-agent research:** orchestrator-worker
  with isolated context beats one shared transcript.
- **LangGraph:** `interrupt`/`Command(resume)` remain HITL/worker checkpoint
  mechanisms. Time-travel is **fork a new ResearchRun from domain state**,
  not arbitrary `update_state` for operators.
- **OpenAI Agents SDK / Google ADK:** comparison only — not adopted.
- **OWASP GenAI / NIST AI RMF:** excessive agency, memory/skill poisoning,
  denial-of-wallet via agent explosion.

## Decision

Keep `ResearchOrchestrator` as lifecycle authority. Add policy modules:

| Module | Role |
|---|---|
| ContextAssembly + ContextBudget | assemble/filter/compact/isolate |
| Compaction | deterministic; never evidence-as-summary |
| WorkingMemory + AgentNote | bounded, typed, no CoT |
| Skill catalog (SKILL.md) | procedure only |
| SkillRouter | keyword/task match, max 2 skills |
| AllocationPolicy | concurrency class from DAG shape + budget |
| DelegationPolicy | max_depth=1 (orchestrator→workers) |
| AgentFactory | typed worker spec |
| SufficiencyEvaluator | informs stop; termination remains deterministic |
| ReplanEvaluator | bounded DAG patch |
| ToolRegistry | capability metadata + progressive disclosure |
| Config snapshot | reproducibility |
| Fork | new run + parent_id; no approval reuse |

## Rejected

CrewAI, AutoGen, OpenAI Agents SDK, Google ADK as runtime. Redis. Semantic
answer cache. Cross-run generic memory (Wiki remains the compiled knowledge
path). Auto-promoted LLM skills. Unbounded nested agents. LangGraph raw
checkpoint mutation APIs.

## HITL

ADR-011 remains authoritative. Runtime fork/replay must not reuse operational
approvals. Skills cannot authorize HITL actions.
