"""Structured offline LLM judges — never attached to 100% online traffic."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class JudgeVerdict(BaseModel):
    score: float = Field(ge=0, le=1)
    verdict: Literal["pass", "fail"]
    rationale: str = Field(max_length=400)
    rubric_id: str
    evaluator_version: str
    provider: str | None = None
    model: str | None = None


RUBRICS: dict[str, str] = {
    "hallucination": (
        "Fail if the answer invents facts not supported by the reference context. "
        "Pass if every material claim is grounded. Score 1 grounded, 0 invented."
    ),
    "correctness": (
        "Compare the answer to the reference. Pass if the core factual conclusion matches. "
        "Do not reward extra unsupported detail."
    ),
    "answer_relevance": (
        "Pass if the answer addresses the research goal. Fail if it is off-topic."
    ),
    "task_completion": (
        "Pass if the output would satisfy the stated task. Fail if required parts are missing."
    ),
    "conciseness": (
        "Pass if the answer is compact without omitting required facts. Fail if padded or truncated badly."
    ),
    "plan_quality": (
        "Pass if the plan decomposes the goal into useful, non-redundant tasks. Fail if tasks are empty or off-goal."
    ),
    "synthesis_quality": (
        "Pass if synthesis compares sources and states uncertainty. Fail if it merely lists snippets."
    ),
    "report_completeness": (
        "Pass if the report covers goal, findings, and caveats. Fail if a required section is missing."
    ),
}

JUDGE_VERSION = "semantic-offline-v1"
