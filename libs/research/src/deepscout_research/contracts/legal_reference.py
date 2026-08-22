"""Legal reference discovery and primary-legislation lookup planning."""

from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

from deepscout_core.domain.contracts import LegalReference

_ARTICLE_RE = re.compile(
    r"\b(?:article|articolo|art\.?)\s*(\d+[a-z]?(?:\s*\(\d+\))?)",
    re.I,
)
_REGULATION_RE = re.compile(
    r"\b(?:regulation|regolamento|directive|direttiva)\s*"
    r"(?:\(?(?:EU|UE)\)?\s*)?(?:No\.?|n\.?)?\s*(\d{4}/\d+)",
    re.I,
)
_CELEX_RE = re.compile(r"\bCELEX[:\s]*(\d{4}[A-Z]\d+)", re.I)
_CELEX_URL_RE = re.compile(r"eur-lex\.europa\.eu/.+CELEX:(\d{4}[A-Z]\d+)", re.I)


def extract_legal_references(text: str, *, source_url: str = "") -> list[LegalReference]:
    references: list[LegalReference] = []
    seen: set[str] = set()
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if len(sentence) < 20:
            continue
        instrument = ""
        reg_match = _REGULATION_RE.search(sentence)
        if reg_match:
            instrument = f"Regulation (EU) {reg_match.group(1)}"
        celex_match = _CELEX_RE.search(sentence) or (
            _CELEX_URL_RE.search(source_url) if source_url else None
        )
        if celex_match and not instrument:
            instrument = f"CELEX:{celex_match.group(1)}"
        article_match = _ARTICLE_RE.search(sentence)
        if not instrument and not article_match:
            continue
        article = article_match.group(1) if article_match else ""
        key = f"{instrument}|{article}"
        if key in seen:
            continue
        seen.add(key)
        references.append(
            LegalReference(
                instrument=instrument[:500],
                article=article[:64],
                topic=sentence[:500],
                source_url=source_url[:2048],
            )
        )
    return references[:10]


def primary_legal_lookup_urls(reference: LegalReference) -> list[str]:
    urls: list[str] = []
    celex = None
    if reference.instrument.startswith("CELEX:"):
        celex = reference.instrument.split(":", 1)[1]
    else:
        reg = re.search(r"(\d{4}/\d+)", reference.instrument)
        if reg:
            year, number = reg.group(1).split("/")
            celex = f"{year}R{number.zfill(4)}" if len(number) <= 4 else f"{year}R{number}"
    if celex:
        urls.append(f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}")
        if reference.article:
            urls.append(
                f"https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX:{celex}#art_{reference.article.split('(')[0]}"
            )
    return urls[:3]


def institutional_profile_url_hints(office_title: str) -> list[str]:
    """Bounded institutional profile URLs derived from office title metadata (not person names)."""
    lowered = office_title.casefold()
    if "president" in lowered and "commission" in lowered:
        return [
            "https://commission.europa.eu/about/president-european-commission_en",
            "https://commission.europa.eu/about/organisation/president_en",
        ]
    return []


def discover_official_links(html_or_text: str, base_url: str) -> list[str]:
    """Discover institutional profile/leadership URLs from page content."""
    found: list[str] = []
    host = urlparse(base_url).netloc.lower()
    patterns = (
        r'href=["\']([^"\']*(?:president|presidente|leadership|about|college|commissioners)[^"\']*)["\']',
        r'https?://[^\s<>"\']+(?:president|presidente|leadership|about)[^\s<>"\']*',
    )
    for pattern in patterns:
        for match in re.finditer(pattern, html_or_text, re.I):
            raw = match.group(1) if match.lastindex else match.group(0)
            if raw.startswith("/"):
                raw = urljoin(base_url, raw)
            if not raw.startswith("http"):
                continue
            link_host = urlparse(raw).netloc.lower()
            if host and host not in link_host and "europa.eu" not in link_host:
                continue
            if any(token in raw.casefold() for token in ("president", "presidente", "leadership", "about", "college")):
                found.append(raw.split("#")[0])
    return list(dict.fromkeys(found))[:5]
