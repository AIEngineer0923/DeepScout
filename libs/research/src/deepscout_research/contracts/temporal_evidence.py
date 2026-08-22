"""Domain-agnostic temporal proposition detection in evidence text."""

from __future__ import annotations

import re

_APPLICABLE_NOW = (
    "already applicable",
    "already in force",
    "in force",
    "entered into application",
    "enters into application",
    "applies from",
    "shall apply from",
    "effective from",
    "già applicab",
    "in vigore",
    "entrata in vigore",
    "entrano in vigore",
    "entra in vigore",
    "applicabili da",
    "a partire da",
    "applies as of",
    "pubblicato il",
    "published on",
)

_FUTURE_OR_TRANSITIONAL = (
    "transitional",
    "transition period",
    "by 20",
    "from 20",
    "until 20",
    "later obligation",
    "future obligation",
    "successiv",
    "transitori",
    "decorrenza successiva",
    "shall comply by",
    "deadline",
    "postponed to",
    "not before",
    "entro il",
    "by august 2027",
    "2027",
    "2028",
)

_ENFORCEMENT = (
    "enforcement",
    "enforce",
    "penalt",
    "sanction",
    "supervisory",
    "applicazione",
    "sanzion",
)


def _has_year(text: str) -> bool:
    return bool(re.search(r"\b20\d{2}\b", text))


def evidence_supports_applicable_now(*, statement: str, quote: str) -> bool:
    combined = f"{statement} {quote}".casefold()
    if not any(signal in combined for signal in _APPLICABLE_NOW):
        return False
    return (
        _has_year(combined)
        or "already" in combined
        or "già" in combined
        or "in force" in combined
        or "in vigore" in combined
        or "entra in vigore" in combined
        or "entrano in vigore" in combined
        or "a partire da" in combined
    )


def evidence_supports_future_or_transitional(*, statement: str, quote: str) -> bool:
    combined = f"{statement} {quote}".casefold()
    if any(signal in combined for signal in _FUTURE_OR_TRANSITIONAL):
        return True
    if "from" in combined and _has_year(combined):
        years = [int(match) for match in re.findall(r"\b(20\d{2})\b", combined)]
        if years and max(years) >= 2027:
            return True
    return False


def evidence_supports_enforcement_timing(*, statement: str, quote: str) -> bool:
    combined = f"{statement} {quote}".casefold()
    return any(signal in combined for signal in _ENFORCEMENT) and _has_year(combined)
