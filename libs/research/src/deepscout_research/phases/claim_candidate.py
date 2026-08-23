"""Admission rules for sentences that may become claims.

Snapshot text is whatever the fetcher extracted from a page, so it contains
navigation bars, headlines, bylines, related-article lists and player controls
alongside prose. Those fragments score well on keyword overlap — a nav bar is
dense in topical nouns — and once admitted they become a claim whose evidence
quote is the fragment itself, so verification passes trivially.

The checks here are structural rather than topical: they look at how the text
is shaped, not what it is about, so they apply to any research domain.
"""

from __future__ import annotations

import re

# Characters used to separate navigation items, breadcrumbs and title/site
# suffixes. They are vanishingly rare inside a prose sentence.
_SEPARATORS = ("|", "·", "•", "»", "›", "▸", "❯")

# Generic page furniture. These are properties of web pages, not of any subject
# area, so the list stays short and does not grow per demo topic.
_CHROME_MARKERS = (
    "for more information",
    "latest stories",
    "play pause",
    "read more",
    "share this",
    "skip to content",
    "sign in",
    "subscribe",
    "all rights reserved",
    "privacy policy",
    "terms of use",
    "cookie",
    "key takeaways",
    "tl;dr",
)

_MIN_WORDS = 8
# A headline capitalises its content words, so Title Case arrives in unbroken
# runs. Prose capitalises isolated proper nouns, which lowercase function words
# keep breaking up. Requiring both a long run and a high overall share keeps
# sentences that merely name a long institution ("the European Commission Joint
# Research Centre published...") out of the reject pile.
_MAX_TITLE_CASE_RUN = 4
_MAX_TITLE_CASE_RATIO = 0.35
_REPEAT_WINDOW = 8

_LEADING_DATE_FRAGMENT = re.compile(r"^\d{1,2},\s")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _is_cased(word: str) -> bool:
    """True for words in a script that distinguishes upper from lower case."""
    return bool(word) and word[:1].isalpha() and word.lower() != word.upper()


def _title_case_shape(words: list[str]) -> tuple[int, float]:
    """Longest unbroken Title Case run, and the overall Title Case share.

    Words in uncased scripts count as neither, so both figures stay at zero for
    languages without capitalisation.
    """
    cased = [w for w in words[1:] if _is_cased(w)]
    if len(cased) < 4:
        return 0, 0.0
    longest = run = 0
    for word in cased:
        if word[:1].isupper():
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    shouty = sum(1 for w in cased if len(w) >= 3 and w[:1].isupper())
    scored = sum(1 for w in cased if len(w) >= 3)
    return longest, (shouty / scored if scored else 0.0)


def _repeats_a_window(words: list[str]) -> bool:
    """True when a long run of words appears twice — a duplicated headline."""
    if len(words) < _REPEAT_WINDOW * 2:
        return False
    seen: set[str] = set()
    for index in range(len(words) - _REPEAT_WINDOW + 1):
        window = " ".join(words[index : index + _REPEAT_WINDOW]).casefold()
        if window in seen:
            return True
        seen.add(window)
    return False


def claim_candidate_rejection(text: str) -> str | None:
    """Why this text cannot become a claim, or None when it is admissible."""
    stripped = text.strip()
    if not stripped:
        return "empty"

    words = stripped.split()
    if len(words) < _MIN_WORDS:
        return "too_short"

    if any(sep in stripped for sep in _SEPARATORS):
        return "navigation_separator"

    lowered = stripped.casefold()
    if any(marker in lowered for marker in _CHROME_MARKERS):
        return "page_chrome"

    if _LEADING_DATE_FRAGMENT.match(stripped):
        return "truncated_start"
    first = _WORD.search(stripped)
    if first is not None and first.start() == 0:
        token = first.group(0)
        # A sentence split mid-word leaves a short lowercase remnant ("es history").
        if token[:1].islower() and token.lower() != token.upper() and len(token) < 4:
            return "truncated_start"

    if _repeats_a_window(words):
        return "repeated_span"

    run, ratio = _title_case_shape(words)
    if run >= _MAX_TITLE_CASE_RUN and ratio > _MAX_TITLE_CASE_RATIO:
        return "headline_case"

    return None


def is_claim_candidate(text: str) -> bool:
    return claim_candidate_rejection(text) is None
