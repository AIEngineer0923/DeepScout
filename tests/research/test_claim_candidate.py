"""Claim admission regression corpus.

Every REJECTED sample below was a real stored claim on a published public demo
before this filter existed: navigation bars, headlines, bylines and mid-word
fragments, all marked verified because the claim text was its own evidence
quote. Every ADMITTED sample was a genuine claim from the same runs.
"""

from __future__ import annotations

import pytest
from deepscout_research.phases.claim_candidate import (
    claim_candidate_rejection,
    is_claim_candidate,
)

REJECTED: list[tuple[str, str]] = [
    (
        "navigation_separator",
        "Latest Stories Engineering Semiconductor Display Panel Battery Supply Chain "
        "Defense·Energy Biotech IT·Gaming Telecom Hyun-Seon, Park Published 2026.08.19",
    ),
    (
        "navigation_separator",
        "The Enterprise Semantic Backbone A Foundation for Reliable and Scalable "
        "Agentic AI | IndustryWeek",
    ),
    (
        "page_chrome",
        "For more information Press release: Commission starts enforcing AI Act rules "
        "Press release: Guidelines on transparency obligations Frequently asked questions",
    ),
    (
        "repeated_span",
        "Anthropic Opus 5 and the $965B IPO Thesis: Why Capability Alone No Longer Sets "
        "the Valuation Floor - FourWeekMBA Anthropic Opus 5 and the $965B IPO Thesis: "
        "Why Capability Alone No Longer Sets the Valuation Floor AI Business Brief",
    ),
    (
        "truncated_start",
        "es history; verifying that a component is free from vulnerabilities registered "
        "in the European vulnerability database established pursuant to Article 12",
    ),
    (
        "truncated_start",
        "18, 2026 (GLOBE NEWSWIRE) -- Synthesized, the AI-native test infrastructure "
        "company, today announced its Test Data Agent, a new agentic infrastructure",
    ),
    (
        "headline_case",
        "LFP Vs NMC Battery: A Technical Comparison Of Cycle Life, Safety, And Cost - BSLBATT",
    ),
    (
        "page_chrome",
        "Similar content being viewed by others Introducing untargeted data-independent "
        "acquisition for metaproteomics of complex microbial samples",
    ),
    (
        "headline_case",
        "RAG AI Development for Enterprise Applications: 2026 Guide Decoding The Concept "
        "of Outsourcing Software Development: A Complete Guide The Complete Guide",
    ),
]

ADMITTED: list[str] = [
    "According to the ICCT 2025 lifecycle analysis , a BEV in Europe will offset its "
    "higher manufacturing emissions after about 17,000 km (roughly 10,500 miles).",
    "Because it can be difficult to “untrain” an AI model, it is important to examine "
    "training and RAG database data before any training or retrieval occurs.",
    "These systems store documents, handle matter inception and track time, but none of "
    "them individually hold the full context of a matter in one place.",
    "The Commission will publish guidelines on the application of the requirements and "
    "obligations referred to in Articles 8 to 15 and in Article 25 AI Act",
    "Regarding CO 2 emissions, it is clear that there is a great difference between "
    "internal combustion engine vehicles (ICEV) and battery electric vehicles.",
    "The delayed availability of the standards puts in jeopardy the successful entry "
    "into application of the high-risk rules on 2 August 2026.",
]


@pytest.mark.parametrize(("reason", "text"), REJECTED, ids=[r for r, _ in REJECTED])
def test_page_furniture_never_becomes_a_claim(reason: str, text: str) -> None:
    assert claim_candidate_rejection(text) == reason


@pytest.mark.parametrize("text", ADMITTED)
def test_real_claims_are_still_admitted(text: str) -> None:
    assert is_claim_candidate(text), claim_candidate_rejection(text)


def test_uncased_scripts_are_not_penalised_for_capitalisation() -> None:
    # Title-case scoring is meaningless without case; it must not reject prose
    # in scripts that have none.
    japanese = "".join(
        [
            "この報告書は、欧州における",
            "電気自動車のライフサイクル",
            "排出量を、従来の内燃機関車",
            "と比較して評価しています。",
        ]
    )
    assert claim_candidate_rejection(japanese) != "headline_case"


def test_temporal_extraction_ignores_a_bare_year_beside_applications() -> None:
    from deepscout_research.contracts.temporal_claims import extract_temporal_claims

    text = (
        "Battery electric vehicle applications have grown steadily since 2019 across "
        "several European markets, according to registration data."
    )
    assert extract_temporal_claims(text) == []
