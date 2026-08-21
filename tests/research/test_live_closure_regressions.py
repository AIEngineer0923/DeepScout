"""Workspace, retrieval, HITL, and health performance/correctness regressions."""

from __future__ import annotations

import inspect
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from deepscout_core.domain.enums import CostReportStatus
from deepscout_core.domain.schemas import ResearchRunCreate
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_research.hitl import HumanReviewService
from deepscout_research.orchestrator import ResearchOrchestrator
from deepscout_research.retrieval.models import RetrievalQuery
from deepscout_research.retrieval.service import RetrievalService
from deepscout_research.retrieval.spec import EmbeddingSpec
from deepscout_research.routing.provider_health import ProviderHealthRegistry

from deepscout_api.workspace import assemble_workspace


def test_wiki_compiles_after_report() -> None:
    source = inspect.getsource(ResearchOrchestrator._run_post_research_phases)
    assert source.index("generate_report") < source.index("_compile_knowledge_phase")


def test_provider_health_is_thread_safe_and_isolates_providers() -> None:
    health = ProviderHealthRegistry(failure_threshold=80, cooldown_s=30.0)

    def worker(_index: int) -> None:
        for _ in range(40):
            health.record_failure(ProviderKind.GOOGLE, reason="429")
            assert health.is_available(ProviderKind.OPENAI) is True
            health.record_success(ProviderKind.ANTHROPIC)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(worker, range(8)))
    assert health.is_available(ProviderKind.OPENAI) is True
    assert health.is_available(ProviderKind.ANTHROPIC) is True
    assert health.is_available(ProviderKind.GOOGLE) is False


def test_hybrid_retrieval_overlaps_embedding_with_lexical(monkeypatch: pytest.MonkeyPatch) -> None:
    spec = EmbeddingSpec(provider="google", model="test", dimensions=8, config_version="v1")
    store = MagicMock()
    store.get_run.return_value = SimpleNamespace(id=uuid.uuid4())
    store._session = object()
    store.list_snapshots_for_run.return_value = []
    service = RetrievalService(store, Settings(_env_file=None), client=object(), spec=spec)

    def slow_embed(_client, _query):
        time.sleep(0.12)
        return [0.0] * 8

    def slow_lexical(*_args, **_kwargs):
        time.sleep(0.12)
        return []

    monkeypatch.setattr("deepscout_research.retrieval.service.embed_query", slow_embed)
    monkeypatch.setattr("deepscout_research.retrieval.service.lexical_search", slow_lexical)
    monkeypatch.setattr("deepscout_research.retrieval.service.dense_search", lambda *a, **k: [])
    started = time.perf_counter()
    result = service._search_once(
        RetrievalQuery(query="battery chemistry", run_id=uuid.uuid4(), apply_rerank=False)
    )
    elapsed = time.perf_counter() - started
    assert result == []
    assert elapsed < 0.22


@pytest.mark.postgres
def test_workspace_skips_evals_while_run_is_active(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="Pending workspace eval skip"), settings)
    with patch("deepscout_api.workspace.evaluate_research_run") as mocked:
        mocked.side_effect = AssertionError("evals must not run for non-terminal workspace")
        payload = assemble_workspace(store, run.id)
    assert payload["evaluations"] == []
    assert payload["evaluations_deferred"] is True
    assert "db_load" in payload["timings_ms"]


@pytest.mark.postgres
def test_hitl_payload_keeps_unknown_cost(store, settings) -> None:
    run = store.create_run(ResearchRunCreate(goal="HITL unknown cost"), settings)
    row = store.get_run_row(run.id)
    assert row is not None
    row.cost_report_status = CostReportStatus.UNKNOWN
    row.consumed_cost_usd = 0.0
    service = HumanReviewService(store, settings)
    review_id = service.create_budget_extension_review(run.id)
    review = store.get_review_request(review_id)
    assert review is not None
    assert review.proposed_action_payload.get("consumed_cost_usd") is None
    assert review.proposed_action_payload.get("cost_status") == "unknown"
