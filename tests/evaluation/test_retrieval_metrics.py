from deepscout_evaluation.retrieval_metrics import (
    duplicate_candidate_rate,
    hit_at_k,
    mrr,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def test_recall_at_k() -> None:
    assert recall_at_k(relevant_found=2, total_relevant=4, k=3) == 0.5


def test_precision_at_k() -> None:
    assert precision_at_k(relevant_found=2, returned=5, k=3) == 2 / 3


def test_mrr_first_hit() -> None:
    assert mrr(first_relevant_rank=2) == 0.5


def test_hit_at_k() -> None:
    assert hit_at_k(relevant_found=1, k=5) == 1.0
    assert hit_at_k(relevant_found=0, k=5) == 0.0


def test_ndcg_perfect_ranking() -> None:
    assert ndcg_at_k(gains=[1.0, 0.0, 0.0], k=3) == 1.0


def test_duplicate_rate() -> None:
    assert duplicate_candidate_rate(total=4, unique_snapshots=3) == 0.25
