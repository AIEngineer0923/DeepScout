"""Evidence relevance and claim specificity validation."""

from __future__ import annotations

import re

from deepscout_core.domain.contracts import AnswerRequirement, ResearchContract

_NOISE_HINTS = (
    "morrisons",
    "humanitarian",
    "recipe",
    "coupon",
    "shopping",
    "stock price unrelated",
)


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]{3,}", text.casefold())}


def relevance_score(
    *,
    quote: str,
    query: str,
    goal: str,
    requirement: AnswerRequirement | None = None,
) -> int:
    text = quote.casefold()
    for hint in _NOISE_HINTS:
        if hint in text and hint not in goal.casefold():
            return 0
    target = _tokens(" ".join(filter(None, [goal, query, requirement.text if requirement else ""])))
    quote_tokens = _tokens(quote)
    if not target:
        return 0
    score = len(target & quote_tokens)
    for token in _tokens(query):
        if len(token) >= 3 and token in text:
            score += 1
    return score


def is_evidence_relevant(
    *,
    quote: str,
    query: str,
    goal: str,
    contract: ResearchContract | None = None,
    requirement: AnswerRequirement | None = None,
    min_score: int = 2,
) -> bool:
    score = relevance_score(quote=quote, query=query, goal=goal, requirement=requirement)
    if score < min_score:
        return False
    if contract is not None:
        goal_tokens = _tokens(contract.primary_question)
        quote_tokens = _tokens(quote)
        if goal_tokens and len(goal_tokens & quote_tokens) == 0 and score < 3:
            return False
    return True


_NUMERIC_PATTERN = re.compile(
    r"(?<!\w)(?:\d{1,3}(?:[.,]\d{3})*(?:[.,]\d+)?|\d+(?:\.\d+)?)\s*(?:%|°c|km|kg|g/km|g co2|wh/kg|years?|months?)?",
    re.I,
)


def extract_numeric_spans(text: str) -> list[str]:
    return [match.group(0).strip() for match in _NUMERIC_PATTERN.finditer(text)]


def _normalize_number(value: str) -> str:
    cleaned = value.strip().casefold()
    cleaned = cleaned.replace(",", "").replace(" ", "")
    cleaned = re.sub(r"[^0-9.%°a-z/]", "", cleaned)
    return cleaned


def claim_specificity_allowed(*, claim: str, evidence_quote: str) -> bool:
    claim_numbers = extract_numeric_spans(claim)
    if not claim_numbers:
        return True
    evidence_numbers = extract_numeric_spans(evidence_quote)
    if not evidence_numbers:
        return False
    claim_set = {_normalize_number(value) for value in claim_numbers if _normalize_number(value)}
    evidence_set = {
        _normalize_number(value) for value in evidence_numbers if _normalize_number(value)
    }
    if claim_set & evidence_set:
        return True
    # Allow approximate match when claim number is substring of evidence number token.
    for claim_num in claim_set:
        if not claim_num:
            continue
        for evidence_num in evidence_set:
            if claim_num in evidence_num or evidence_num in claim_num:
                return True
    return False
