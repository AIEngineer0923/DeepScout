"""Evidence relevance and claim specificity validation."""

from __future__ import annotations

import re

from deepscout_core.domain.contracts import AnswerRequirement, ResearchContract

from deepscout_research.contracts.text_normalize import normalized_research_tokens

_NOISE_HINTS = (
    "morrisons",
    "humanitarian",
    "recipe",
    "coupon",
    "shopping",
    "stock price unrelated",
)

_SUBJECT_STOPWORDS = {
    "analysis",
    "analizza",
    "and",
    "assess",
    "authoritative",
    "available",
    "comparison",
    "compare",
    "con",
    "confronta",
    "credible",
    "current",
    "data",
    "determine",
    "documentation",
    "evidence",
    "evaluate",
    "evaluation",
    "explain",
    "find",
    "for",
    "framework",
    "from",
    "how",
    "identify",
    "including",
    "information",
    "into",
    "method",
    "methods",
    "model",
    "models",
    "new",
    "official",
    "or",
    "original",
    "paper",
    "papers",
    "prefer",
    "production",
    "research",
    "result",
    "results",
    "source",
    "sources",
    "strategy",
    "study",
    "system",
    "systems",
    "that",
    "their",
    "the",
    "this",
    "trade",
    "valuta",
    "vendor",
    "versus",
    "while",
    "what",
    "whether",
    "with",
}


def _topic_anchors(text: str) -> set[str]:
    """Return subject-bearing tokens, excluding research-instruction vocabulary."""
    return {
        token
        for token in _tokens(text) - _SUBJECT_STOPWORDS
        if len(token) >= 3 and not token.isdigit()
    }


def _explicit_identifiers(text: str) -> set[str]:
    identifiers: list[str] = []
    for token in re.findall(r"\b[A-Za-z0-9]{3,128}\b", text):
        is_acronym = token[0].isupper() and token.isupper()
        is_camel_case = (
            token[0].isupper()
            and any(character.islower() for character in token)
            and sum(character.isupper() for character in token) >= 2
        )
        if is_acronym or is_camel_case:
            identifiers.append(token)
    return set().union(*(_tokens(item) for item in identifiers)) if identifiers else set()


def _has_subject_match(*, haystack: set[str], subject: str) -> bool:
    anchors = _topic_anchors(subject)
    overlap = haystack & anchors
    if overlap & _explicit_identifiers(subject):
        return True
    return len(overlap) >= min(2, len(anchors))


def _subject_text(contract: ResearchContract | None, goal: str) -> str:
    primary = contract.primary_question if contract is not None else goal
    subject = re.split(r"[.?!\n]", primary, maxsplit=1)[0]
    subject = re.split(
        r"\b(?:focusing on|evaluate|assess|distinguishing|including|and explain why)\b",
        subject,
        maxsplit=1,
        flags=re.I,
    )[0]
    if re.match(r"^\s*(?:compare|confronta)\b", subject, re.I):
        before_workload = re.split(r"\bfor (?:a|an|the)\b", subject, maxsplit=1, flags=re.I)[0]
        if len(_topic_anchors(before_workload)) >= 3:
            subject = before_workload
    return subject.strip(" ,;:-")


def is_search_result_relevant(
    *,
    title: str,
    snippet: str,
    query: str,
    goal: str,
    contract: ResearchContract | None = None,
) -> bool:
    """Reject search hits with no lexical connection to the assigned subject.

    Search-provider ranking is useful but not an admission decision.  The title
    and snippet must carry either a subject anchor from the user goal or two
    scoped query anchors.  Requiring two query anchors prevents generic words
    such as "evaluation" or "study" from admitting an unrelated paper, while
    still allowing bilingual/reformulated worker queries to bridge languages.
    """
    haystack = _tokens(f"{title} {snippet}")
    if not haystack:
        return False
    subject = _subject_text(contract, goal)
    subject_anchors = _topic_anchors(subject)
    if subject_anchors:
        return _has_subject_match(haystack=haystack, subject=subject)
    query_overlap = haystack & _topic_anchors(query)
    return len(query_overlap) >= 2


def _tokens(text: str) -> set[str]:
    return normalized_research_tokens(text)


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
    target = _topic_anchors(
        " ".join(filter(None, [goal, query, requirement.text if requirement else ""]))
    )
    quote_tokens = _tokens(quote)
    if not target:
        return 0
    score = len(target & quote_tokens)
    for token in _topic_anchors(query):
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
        subject = _subject_text(contract, goal)
        subject_tokens = _topic_anchors(subject)
        if subject_tokens and not _has_subject_match(haystack=quote_tokens, subject=subject):
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
