"""Conservative online evaluation policy for LangSmith attachments."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OnlineEvalRule:
    evaluator_id: str
    sampling_rate: float
    filter_expression: str
    reason: str
    attached: bool


# Cheap deterministic evaluators may run on every root research execution.
# LLM-as-judge evaluators stay offline in development: they spend a second
# model budget that must not mix with application cost, and 5–10% random
# sampling would still be vanity coverage on a tiny local corpus.
ONLINE_EVAL_POLICY: tuple[OnlineEvalRule, ...] = (
    OnlineEvalRule(
        evaluator_id="deepscout-claim-has-evidence",
        sampling_rate=1.0,
        filter_expression="and(eq(is_root, true), eq(name, research_run_execute))",
        reason="Deterministic code evaluator; no extra model spend.",
        attached=True,
    ),
    OnlineEvalRule(
        evaluator_id="llm_judge_hallucination",
        sampling_rate=0.0,
        filter_expression="eq(is_root, true)",
        reason="Semantic judges run offline on a versioned dataset only.",
        attached=False,
    ),
    OnlineEvalRule(
        evaluator_id="llm_judge_answer_relevance",
        sampling_rate=0.0,
        filter_expression="eq(is_root, true)",
        reason="Semantic judges run offline on a versioned dataset only.",
        attached=False,
    ),
)
