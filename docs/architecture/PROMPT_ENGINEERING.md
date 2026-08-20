# Prompt Engineering — DeepScout (August 2026)

Production prompts are versioned artifacts in `libs/research/src/deepscout_research/prompts/`.
Composition follows: **GlobalInvariantPolicy → RoleInstructions → Contracts → RuntimeContext**.

## Official references consulted (implementation date: 2026-08-21)

| Provider / framework | Reference topic |
|---------------------|-----------------|
| Google Gemini | System instruction precedence; structured output; usage metadata |
| OpenAI | Developer/system message hierarchy; JSON schema structured outputs |
| Anthropic | System prompt authority over retrieved content; structured outputs |
| LangChain | `with_structured_output(..., include_raw=True)`; message roles |
| LangGraph | Stateful graphs, checkpoint/resume, conditional critic edges |
| LangSmith | Trace metadata; offline datasets/experiments |

## Design rules

- **Prompt ≠ context**: durable role instructions live in `PromptSpec`; dynamic state uses `compose_runtime_context`.
- **Minimal role-specific instructions**: no filler; security invariants only in `GLOBAL_POLICY_V1`.
- **Structured output**: Pydantic schemas at application boundary.
- **Uncertainty**: typed states are first-class (`INSUFFICIENT_EVIDENCE`, `CONFLICTING`, `UNKNOWN`).
- **Change process**: candidate → dataset → LangSmith experiment → evaluators → PROMOTE/REJECT.

See `PROMPT_MATRIX.md` for per-prompt review records.
