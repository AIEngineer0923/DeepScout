# Agent runtime threats (MODE A)

| ID | Threat | Mitigation |
|---|---|---|
| R1 | Agent explosion via retrieved "spawn 100 agents" | DelegationPolicy + depth=1; injection text cannot spawn |
| R2 | Skill poisoning / self-promotion | Skills loaded from builtin tree only; documents cannot bind |
| R3 | Memory poisoning | Notes are not evidence; Wiki remains provenance-gated |
| R4 | Context injection | Privileged system vs DATA split unchanged |
| R5 | Cache poisoning | No semantic answer cache; snapshot hashes remain content-addressed |
| R6 | Tool/MCP self-authorize | Application ToolRegistry allowlist |
| R7 | Fork reuses HITL approval | New run; reviews not copied; current policy snapshot |
| R8 | Cost amplification | Allocation capped by budget + max_total_workers |
| R9 | Unbounded replan | agent_max_replans + duplicate detection |
| R10 | Nested agents inherit authority | Children (if ever enabled) get sliced tools/budget/depth |
| R11 | Skill binding from Wiki/tool/note text | SkillRouter trusted channel = `task_objective` only |
| R12 | Cache-read inferred as zero | Missing provider cache metadata stays UNKNOWN/None |
| R13 | Isolated worker inherits parent retrieved DATA | `isolate_worker` starts empty retrieved/working state |
| R14 | Unknown privileged tools | ToolRegistry classifies unknown names as DENY |
