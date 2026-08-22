"""Tests for office-holder extraction."""

from deepscout_research.contracts.office_holder import (
    extract_office_holder_evidence,
    verify_office_holder,
)


def test_extract_current_commission_president():
    text = (
        "Ursula von der Leyen is President of the European Commission. "
        "She leads the college of commissioners."
    )
    evidence = extract_office_holder_evidence(
        text,
        source_url="https://commission.europa.eu/about/president-european-commission_en",
    )
    assert evidence is not None
    assert evidence.person_name == "Ursula von der Leyen"
    assert verify_office_holder(evidence)


def test_reject_former_president():
    text = "Jean-Claude Juncker was President of the European Commission from 2014 to 2019."
    evidence = extract_office_holder_evidence(text, source_url="https://ec.europa.eu/example")
    assert evidence is None
