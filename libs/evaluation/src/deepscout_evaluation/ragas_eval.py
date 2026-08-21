"""Optional RAGAS metrics — offline only, requires labeled references."""

from __future__ import annotations


def ragas_available() -> bool:
    try:
        import ragas  # noqa: F401

        return True
    except ImportError:
        return False


def evaluate_ragas_context_precision(
    *, contexts: list[str], question: str, ground_truth: str
) -> float | None:
    """Return RAGAS context precision when ragas is installed and inputs are real."""
    if not ragas_available() or not contexts or not ground_truth.strip():
        return None
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import context_precision

        ds = Dataset.from_dict(
            {
                "question": [question],
                "contexts": [contexts],
                "ground_truth": [ground_truth],
            }
        )
        result = evaluate(ds, metrics=[context_precision])
        value = result["context_precision"]
        return float(value[0]) if value else None
    except Exception:
        return None
