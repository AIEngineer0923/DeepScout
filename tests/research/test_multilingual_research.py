from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from deepscout_core.domain.contracts import (
    LanguageQueryVariant,
    ResearchContract,
    ResearchLanguageStrategy,
    SourceClass,
)
from deepscout_research.contracts.evidence_relevance import is_search_result_relevant
from deepscout_research.contracts.extract import _preferred_classes
from deepscout_research.contracts.query_planning import search_discovery_requests
from deepscout_research.fetch.secure import FetchResult
from deepscout_research.language import detect_language, normalize_language_tag
from deepscout_research.retrieval.fusion import reciprocal_rank_fusion
from deepscout_research.retrieval.models import RetrievedChunk
from deepscout_research.retrieval.rerank import rerank_candidates
from deepscout_research.source_fabric.normalizers import normalize_fetch_result


def _contract() -> ResearchContract:
    return ResearchContract(
        primary_question=(
            "Analizza la durata della garanzia del produttore tedesco e usa le fonti "
            "primarie disponibili. Rispondi in italiano con citazioni verificabili."
        ),
        output_language="it",
        language_strategy=ResearchLanguageStrategy(
            user_language="it",
            output_language="it",
            primary_query_language="de",
            additional_query_languages=["en", "it"],
            expected_primary_source_languages=["de"],
            translation_required=True,
            language_confidence=0.94,
            language_reason="The manufacturer's original warranty is published in German.",
            query_variants=[
                LanguageQueryVariant(
                    language="de",
                    query="Herstellergarantie Batteriesystem Dauer offizielle Garantiebedingungen",
                    requirement_ids=["R0"],
                    expected_primary_source=True,
                ),
                LanguageQueryVariant(
                    language="en",
                    query="manufacturer battery warranty duration official terms",
                    requirement_ids=["R0"],
                ),
                LanguageQueryVariant(
                    language="it",
                    query="durata garanzia batteria condizioni ufficiali produttore",
                    requirement_ids=["R0"],
                ),
            ],
        ),
    )


def test_language_detection_uses_metadata_then_content_and_scripts() -> None:
    assert detect_language("anything", metadata_language="de-DE").language == "de"
    assert (
        detect_language(
            "The official document states that the warranty is valid for users and companies.",
            metadata_language="de-DE",
        ).language
        == "en"
    )
    assert (
        detect_language("Il documento contiene una regola che vale per gli utenti.").language
        == "it"
    )
    assert detect_language("これは日本語の技術文書です。公式情報を説明します。").language == "ja"
    assert normalize_language_tag("Português-BR") == "pt"


def test_quick_multilingual_queries_are_native_bounded_and_goal_conditioned() -> None:
    requests = search_discovery_requests(
        "Verifica la garanzia ufficiale",
        _contract(),
        research_mode="quick",
        max_variants=7,
    )
    assert len(requests) == 2
    assert [item.request.query_language for item in requests] == ["de", "en"]
    assert requests[0].request.query.startswith("Herstellergarantie")
    assert "authoritative primary source evidence" not in requests[0].request.query


def test_native_multilingual_queries_keep_deterministic_source_policy() -> None:
    contract = _contract().model_copy(
        update={"preferred_source_classes": ["software_vendor"]}
    )
    requests = search_discovery_requests(
        "Verifica la garanzia nella documentazione ufficiale",
        contract,
        research_mode="quick",
        max_variants=7,
    )

    assert "official technical documentation" in requests[0].request.query
    assert requests[0].request.query_language == "de"


def test_multilingual_official_documentation_intent_maps_to_vendor_sources() -> None:
    for goal in (
        "Usa prioritariamente documentazione ufficiale.",
        "Utilisez de préférence la documentation officielle.",
        "Bevorzugen Sie die offizielle Dokumentation.",
    ):
        assert "software_vendor" in {item.value for item in _preferred_classes(goal)}


def test_quick_single_language_reserves_a_relaxed_fallback_query() -> None:
    base = _contract()
    english_only = base.language_strategy.model_copy(
        update={
            "primary_query_language": "en",
            "additional_query_languages": [],
            "query_variants": [
                LanguageQueryVariant(
                    language="en",
                    query=(
                        'site:docs.python.org/3.13 "free-threaded" OR '
                        '"free threading" "PEP 703" disable-gil'
                    ),
                    requirement_ids=["R0"],
                    expected_primary_source=True,
                ),
            ],
        }
    )
    contract = base.model_copy(
        update={
            "language_strategy": english_only,
            "preferred_source_classes": [SourceClass.SOFTWARE_VENDOR],
        }
    )

    requests = search_discovery_requests(
        "Spiega il free-threading di Python 3.13",
        contract,
        research_mode="quick",
        max_variants=2,
    )

    assert len(requests) == 2
    assert requests[0].request.query.startswith("site:docs.python.org/3.13 ")
    assert '"free-threaded"' in requests[0].request.query
    assert " OR " in requests[0].request.query
    assert requests[1].request.query != requests[0].request.query
    assert requests[1].request.query.startswith("site:docs.python.org ")
    assert '"' not in requests[1].request.query
    assert " OR " not in requests[1].request.query
    assert [item.request.query_language for item in requests] == ["en", "en"]
    assert "official technical documentation" in requests[1].request.query


def test_cross_language_admission_uses_native_query_without_goal_language_overlap() -> None:
    contract = _contract()
    assert is_search_result_relevant(
        title="Offizielle Herstellergarantie für Batteriesysteme",
        snippet="Die Garantiebedingungen nennen Dauer und Kilometergrenzen.",
        query=contract.language_strategy.query_variants[0].query,
        goal=contract.primary_question,
        contract=contract,
    )
    assert not is_search_result_relevant(
        title="Brot backen am Wochenende",
        snippet="Rezept, Zutaten und Ofentemperatur.",
        query=contract.language_strategy.query_variants[0].query,
        goal=contract.primary_question,
        contract=contract,
    )


def test_cross_language_bridge_survives_policy_enrichment() -> None:
    contract = _contract()
    enriched_query = (
        "Herstellergarantie Batteriesystem Dauer offizielle Garantiebedingungen "
        "official technical documentation"
    )

    assert is_search_result_relevant(
        title="Offizielle Herstellergarantie für Batteriesysteme",
        snippet="Die Garantiebedingungen nennen Dauer und Kilometergrenzen.",
        query=enriched_query,
        goal=contract.primary_question,
        contract=contract,
    )


def test_html_declared_language_is_preserved_for_content_level_detection() -> None:
    normalized = normalize_fetch_result(
        FetchResult(
            url="https://example.invalid/de",
            content_type="text/html; charset=utf-8",
            body=(
                b'<html lang="de-DE"><head><meta property="og:locale" content="de_DE">'
                b"</head><body>Die offizielle Garantie gilt acht Jahre.</body></html>"
            ),
        )
    )
    assert normalized.metadata["declared_language"] in {"de-DE", "de_DE"}
    assert (
        detect_language(
            normalized.text, metadata_language=normalized.metadata["declared_language"]
        ).language
        == "de"
    )


def test_rerank_does_not_erase_dense_cross_language_candidate() -> None:
    run_id = uuid4()
    dense = RetrievedChunk(
        chunk_id=uuid4(),
        snapshot_id=uuid4(),
        source_id=uuid4(),
        run_id=run_id,
        text="Die Herstellergarantie gilt acht Jahre.",
        locator="offset:0-42",
        ordinal=0,
        start_offset=0,
        end_offset=42,
        dense_rank=1,
        fused_score=0.032,
    )
    lexical = dense.model_copy(
        update={
            "chunk_id": uuid4(),
            "snapshot_id": uuid4(),
            "source_id": uuid4(),
            "text": "manufacturer battery warranty duration blog opinion",
            "dense_rank": None,
            "bm25_rank": 1,
            "fused_score": 0.016,
        }
    )
    ranked = rerank_candidates(
        [lexical, dense], query="manufacturer battery warranty duration", limit=2
    )
    assert ranked[0].chunk_id == dense.chunk_id


def test_weighted_rrf_can_preserve_cross_language_dense_rank() -> None:
    dense = uuid4()
    lexical_noise = uuid4()
    fused = reciprocal_rank_fusion(
        [[lexical_noise], [lexical_noise], [dense]],
        weights=[1.0, 1.0, 2.25],
    )
    assert fused[dense] > fused[lexical_noise]


def test_multilingual_benchmark_fixture_covers_required_pairs_and_negative() -> None:
    fixture = json.loads(
        (
            Path(__file__).resolve().parents[2]
            / "libs/evaluation/data/multilingual_retrieval_benchmark_v1.json"
        ).read_text()
    )
    pairs = {item["language_pair"] for item in fixture["retrieval_cases"]}
    assert {"it-en", "it-de", "en-it", "fr-en", "de-en", "it-none"} <= pairs
    assert any(item["id"] == "alias-fr-en" for item in fixture["retrieval_cases"])
    assert any(item["id"] == "identifier-cross-language" for item in fixture["retrieval_cases"])
