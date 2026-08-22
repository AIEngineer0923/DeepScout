"""Tests for temporal claim extraction and verification."""

from deepscout_core.domain.contracts import TemporalRelation
from deepscout_research.contracts.temporal_claims import (
    extract_temporal_claims,
    requirement_ids_for_temporal_claim,
    verify_temporal_claim,
)


def test_extract_applies_from_claim():
    text = (
        "Providers of general-purpose AI models shall apply the obligations of Article 53 "
        "from 2 August 2025."
    )
    claims = extract_temporal_claims(text, source_url="https://eur-lex.europa.eu/example")
    assert claims
    claim = claims[0]
    assert claim.verified
    assert claim.temporal_relation == TemporalRelation.APPLIES_FROM
    assert "2025" in claim.date_text


def test_extract_transitional_deadline():
    text = (
        "During the transitional period, providers shall comply by 2 August 2027 "
        "with the transparency obligations for GPAI models."
    )
    claims = extract_temporal_claims(text)
    assert any(claim.temporal_relation == TemporalRelation.MUST_COMPLY_BY for claim in claims)
    assert any("R_reg_later" in requirement_ids_for_temporal_claim(c) for c in claims)


def test_verify_requires_date_and_subject():
    from deepscout_core.domain.contracts import TemporalClaim

    claim = TemporalClaim(
        subject="GPAI provider obligation",
        obligation="test",
        temporal_relation=TemporalRelation.APPLIES_FROM,
        date_text="2026",
        evidence_quote="short",
    )
    assert not verify_temporal_claim(claim)
