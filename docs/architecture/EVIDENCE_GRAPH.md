# Evidence Graph

DeepScout's differentiator: **source-aware evidence**, not LLM monologue.

## Graph structure

```text
ResearchRun
  └── Source ──► SourceSnapshot (immutable)
         └── Claim ──► Evidence (quote + span → snapshot)
                └── Contradiction (claim ↔ claim)
  └── WikiPage / WikiStatement (compiled, derived; never evidence)
  └── Decision (derived from verified claims only)
  └── Report (citations from evidence graph)
```

## Invariants

1. **Claim without Evidence** → neither `verified` nor `partially_verified`
2. **One matching source** → at most `partially_verified`; `verified` requires matching
   evidence from at least two distinct sources
3. **Decision/Report** uses only `verified` or `partially_verified` claims
4. **SourceSnapshot** is immutable; re-fetch creates new snapshot
5. **Contradiction** requires evidence on both sides or `insufficient_evidence` flag
6. LLM-generated text is **never** authoritative without evidence link
7. **WikiStatement** must resolve to Claim → Evidence → SourceSnapshot when treated as factual; wiki text alone is not evidence

## Verification states

`pending` → `supported` → `verified` | `partially_verified` | `refuted` | `insufficient_evidence`

## Confidence

Confidence scores are computed from:

- Evidence support strength
- Source trust tier
- Verifier/critic structured output
- Contradiction presence

Not from model fluency alone.

## UI contract

Product UI shows:

- Claims with linked sources
- Evidence quotes with snapshot references
- Contradictions and gaps
- Decision confidence with dissent notes

Product UI does **not** show raw LangSmith chain-of-thought.
