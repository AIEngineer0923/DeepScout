"""Unit tests for compiled knowledge planner routing and export sanitization."""

from __future__ import annotations

import uuid

from deepscout_core.domain.enums import AgentRole
from deepscout_core.settings import Settings
from deepscout_core.types import ProviderKind
from deepscout_research.knowledge.obsidian_export import sanitize_export_text
from deepscout_research.retrieval.planner import plan_retrieval_query


def test_planner_routes_compiled_corpus() -> None:
    settings = Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE)
    plan = plan_retrieval_query(
        query="What have we learned about solid-state batteries?",
        run_id=uuid.uuid4(),
        settings=settings,
        document_token_estimate=5000,
    )
    assert plan.corpus == "compiled"


def test_planner_routes_raw_evidence_lookup() -> None:
    settings = Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE)
    plan = plan_retrieval_query(
        query="Find evidence and quote the exact passage about CVE-2024-1234",
        run_id=uuid.uuid4(),
        settings=settings,
        role=AgentRole.VERIFIER,
        document_token_estimate=5000,
    )
    assert plan.corpus == "raw"


def test_planner_routes_contradiction_to_both() -> None:
    settings = Settings(_env_file=None, LLM_PROVIDER=ProviderKind.GOOGLE)
    plan = plan_retrieval_query(
        query="What contradicts the commercialization claim?",
        run_id=uuid.uuid4(),
        settings=settings,
        document_token_estimate=5000,
    )
    assert plan.corpus == "both"


def test_export_sanitizes_javascript_and_html() -> None:
    dirty = 'Click <a href="javascript:alert(1)">here</a> now'
    cleaned = sanitize_export_text(dirty)
    assert "javascript" not in cleaned.lower()
    assert "<a" not in cleaned
