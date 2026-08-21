# HITL threat model (MODE A)

| ID | Threat | Mitigation |
|---|---|---|
| H1 | Model self-approval | `is_authoritative_approval` rejects non api/ui/operator |
| H2 | RAG/Wiki/tool spoof text | Spoof patterns are DATA; never resolve reviews |
| H3 | LangSmith feedback as auth | Separate `human_feedback` table; no resolve path |
| H4 | Approval substitution | `payload_hash` binding; edit via schema only |
| H5 | Replay / double approve | Idempotent resolve; budget applied once |
| H6 | Cross-run IDOR | run_id must match review.research_run_id |
| H7 | Stale after cancel | cancel supersedes pending reviews |
| H8 | Expiry TOCTOU | expired → fail closed, never auto-approve |
| H9 | Busy-wait workers | PAUSED returns immediately; resume via job |
| H10 | Nested LLM retries on resume | Transport max_retries=0 unchanged |
