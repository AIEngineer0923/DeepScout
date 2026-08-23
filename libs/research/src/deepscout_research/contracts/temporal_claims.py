"""Structured temporal claim extraction and verification from legal/official text."""

from __future__ import annotations

import re

from deepscout_core.domain.contracts import TemporalClaim, TemporalRelation

_DATE_RE = re.compile(
    r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|"
    r"gennaio|febbraio|marzo|aprile|maggio|giugno|luglio|agosto|settembre|ottobre|novembre|dicembre)\s+20\d{2}|\d{4}-\d{2}-\d{2}|20\d{2})\b",
    re.I,
)

_RELATION_PATTERNS: tuple[tuple[re.Pattern[str], TemporalRelation], ...] = (
    (re.compile(r"\bshall apply\b.*\bfrom\b", re.I), TemporalRelation.APPLIES_FROM),
    (re.compile(r"\bshall apply (?:from|as of)\b", re.I), TemporalRelation.APPLIES_FROM),
    (re.compile(r"\bappl(?:y|ies|icable) (?:from|as of)\b", re.I), TemporalRelation.APPLIES_FROM),
    (re.compile(r"\bentered into (?:force|application)\b", re.I), TemporalRelation.ENTERED_INTO_FORCE),
    (re.compile(r"\bentr(?:a|ano) in vigore\b", re.I), TemporalRelation.ENTERED_INTO_FORCE),
    (re.compile(r"\ba partire da\b", re.I), TemporalRelation.APPLIES_FROM),
    (re.compile(r"\bgià applicab", re.I), TemporalRelation.APPLIES_FROM),
    (re.compile(r"\bshall comply by\b", re.I), TemporalRelation.MUST_COMPLY_BY),
    (re.compile(r"\bby\s+\d", re.I), TemporalRelation.MUST_COMPLY_BY),
    (re.compile(r"\bentro il\b", re.I), TemporalRelation.MUST_COMPLY_BY),
    (re.compile(r"\buntil\b", re.I), TemporalRelation.TRANSITION_UNTIL),
    (re.compile(r"\btransitional\b", re.I), TemporalRelation.TRANSITION_UNTIL),
    (re.compile(r"\btransitori", re.I), TemporalRelation.TRANSITION_UNTIL),
    (re.compile(r"\benforce(?:ment|able)\b", re.I), TemporalRelation.ENFORCEABLE_FROM),
    (re.compile(r"\bapplicazione\b", re.I), TemporalRelation.ENFORCEABLE_FROM),
)


_RELATION_PHRASES: dict[TemporalRelation, str] = {
    TemporalRelation.APPLIES_FROM: "applies from",
    TemporalRelation.ENFORCEABLE_FROM: "is enforceable from",
    TemporalRelation.ENTERED_INTO_FORCE: "entered into force on",
    TemporalRelation.MUST_COMPLY_BY: "must be complied with by",
    TemporalRelation.TRANSITION_UNTIL: "has a transition period until",
    TemporalRelation.SUPERSEDED_FROM: "is superseded from",
}

_MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)


def readable_date(date_text: str) -> str:
    """ISO dates read as prose; year-only and already-prose dates pass through."""
    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", date_text.strip())
    if not iso:
        return date_text.strip()
    year, month, day = iso.groups()
    index = int(month)
    if not 1 <= index <= 12:
        return date_text.strip()
    return f"{int(day)} {_MONTHS[index - 1]} {year}"


def temporal_claim_statement(claim: TemporalClaim) -> str:
    """Human-readable claim text.

    Claim statements are stored and shown to users, so they must never carry the
    raw enum value (`applies_from`) or an unformatted ISO date.
    """
    subject = claim.subject.strip() or "General obligation"
    subject = subject[0].upper() + subject[1:]
    scope = f" ({claim.applicability_scope.strip()})" if claim.applicability_scope.strip() else ""
    phrase = _RELATION_PHRASES.get(claim.temporal_relation, "applies from")
    return f"{subject}{scope} {phrase} {readable_date(claim.date_text)}".strip()


def _extract_date(text: str) -> str:
    match = _DATE_RE.search(text)
    return match.group(1) if match else ""


def _subject_scope(sentence: str) -> tuple[str, str]:
    lowered = sentence.casefold()
    subject = "general obligation"
    if "gpai" in lowered or "general purpose" in lowered or "general-purpose" in lowered:
        subject = "GPAI provider obligation"
    elif "systemic risk" in lowered or "rischio sistemico" in lowered:
        subject = "systemic-risk GPAI obligation"
    elif "transparency" in lowered or "trasparenza" in lowered:
        subject = "transparency obligation"
    elif "high-risk" in lowered or "alto rischio" in lowered:
        subject = "high-risk AI obligation"
    article = re.search(r"\b(?:article|articolo|art\.?)\s*(\d+[a-z]?(?:\s*\(\d+\))?)", sentence, re.I)
    scope = f"Article {article.group(1)}" if article else ""
    return subject, scope


def extract_temporal_claims(text: str, *, source_url: str = "") -> list[TemporalClaim]:
    claims: list[TemporalClaim] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if len(sentence) < 25 or not re.search(r"\b20\d{2}\b", sentence):
            continue
        relation: TemporalRelation | None = None
        for pattern, rel in _RELATION_PATTERNS:
            if pattern.search(sentence):
                relation = rel
                break
        if relation is None:
            lowered = sentence.casefold()
            if re.search(r"\bfrom\b", lowered) and any(
                token in lowered for token in ("applic", "obligation", "provider", "gpai", "vigore")
            ):
                relation = TemporalRelation.APPLIES_FROM
            else:
                # A bare year next to the word "applications" is not a legal
                # commencement date. Without an explicit relation phrase there
                # is nothing to assert, so the sentence is skipped.
                continue
        date_text = _extract_date(sentence)
        if not date_text:
            continue
        subject, scope = _subject_scope(sentence)
        claim = TemporalClaim(
            subject=subject,
            obligation=sentence[:1000],
            temporal_relation=relation,
            date_text=date_text,
            applicability_scope=scope,
            evidence_quote=sentence[:2000],
            source_url=source_url[:2048],
            verified=verify_temporal_claim(
                TemporalClaim(
                    subject=subject,
                    obligation=sentence[:1000],
                    temporal_relation=relation,
                    date_text=date_text,
                    applicability_scope=scope,
                    evidence_quote=sentence[:2000],
                    source_url=source_url,
                )
            ),
        )
        claims.append(claim)
    return claims[:20]


def verify_temporal_claim(claim: TemporalClaim) -> bool:
    quote = claim.evidence_quote.casefold()
    if not claim.date_text or claim.date_text.casefold() not in quote:
        if not re.search(r"\b20\d{2}\b", quote):
            return False
    if not claim.subject:
        return False
    return len(claim.evidence_quote) >= 30


def requirement_ids_for_temporal_claim(claim: TemporalClaim) -> list[str]:
    ids: list[str] = []
    if claim.temporal_relation in {
        TemporalRelation.APPLIES_FROM,
        TemporalRelation.ENTERED_INTO_FORCE,
        TemporalRelation.ENFORCEABLE_FROM,
    }:
        ids.extend(["R_reg_now", "R_reg_current", "R_reg_apply"])
    if claim.temporal_relation in {
        TemporalRelation.TRANSITION_UNTIL,
        TemporalRelation.MUST_COMPLY_BY,
        TemporalRelation.SUPERSEDED_FROM,
    }:
        ids.extend(["R_reg_later", "R_reg_apply"])
    if claim.temporal_relation == TemporalRelation.ENFORCEABLE_FROM:
        ids.append("R_reg_time")
    year_match = re.search(r"(20\d{2})", claim.date_text)
    if year_match and int(year_match.group(1)) >= 2027:
        ids.append("R_reg_later")
    elif year_match and int(year_match.group(1)) <= 2026:
        ids.append("R_reg_now")
    return list(dict.fromkeys(ids))
