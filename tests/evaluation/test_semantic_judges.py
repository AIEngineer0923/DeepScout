from deepscout_evaluation.semantic_judges import JUDGE_VERSION, RUBRICS, JudgeVerdict


def test_rubrics_cover_required_judges() -> None:
    required = {
        "hallucination",
        "correctness",
        "answer_relevance",
        "task_completion",
        "conciseness",
        "plan_quality",
        "synthesis_quality",
        "report_completeness",
    }
    assert required <= set(RUBRICS)
    assert JUDGE_VERSION == "semantic-offline-v1"


def test_verdict_schema_is_structured() -> None:
    ok = JudgeVerdict(
        score=1,
        verdict="pass",
        rationale="Grounded.",
        rubric_id="answer_relevance",
        evaluator_version=JUDGE_VERSION,
    )
    assert ok.verdict == "pass"
