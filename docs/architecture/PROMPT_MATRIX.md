# Prompt Matrix — ACTIVE production prompts

| prompt_id | version | role | status | schema | tools | evaluators |
|-----------|---------|------|--------|--------|-------|------------|
| planner | 1 | PLANNER | ACTIVE | PlannerOutput | none | plan_adherence, task_decomposition |
| research_worker | 1 | RESEARCH_WORKER | ACTIVE | WorkerResult | web_search (allowlist) | worker_task_adherence, tool_selection |
| extractor | 1 | EXTRACTOR | ACTIVE | ClaimWrite | none | quote_exists, unsupported_claim_rate |
| verifier | 1 | VERIFIER | ACTIVE | verification class | none | grounding, citation_correctness |
| critic | 1 | CRITIC | ACTIVE | CriticResult | none | unsupported_claim_rate, synthesis_quality |
| synthesis | 1 | SYNTHESIS | ACTIVE | SynthesisOutput | none | grounding, hallucination |
| report | 1 | REPORT | ACTIVE | ReportWrite | none | citation_correctness, report_completeness |

Implementation: `libs/research/src/deepscout_research/prompts/registry.py`.
