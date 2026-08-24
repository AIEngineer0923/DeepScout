"""Lightweight, auditable language metadata and execution summaries.

This module deliberately avoids a translation dependency. Script detection is
generic; Latin-language hints are a bounded fallback when document metadata is
missing. Unknown remains an honest result instead of a guessed language.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

_LANGUAGE_ALIASES = {
    "english": "en",
    "italian": "it",
    "italiano": "it",
    "french": "fr",
    "français": "fr",
    "german": "de",
    "deutsch": "de",
    "spanish": "es",
    "español": "es",
    "portuguese": "pt",
    "português": "pt",
    "dutch": "nl",
    "polish": "pl",
    "japanese": "ja",
    "korean": "ko",
    "chinese": "zh",
    "arabic": "ar",
}

_LATIN_HINTS: dict[str, frozenset[str]] = {
    "en": frozenset({"the", "and", "with", "from", "this", "that", "for", "are", "was"}),
    "it": frozenset({"che", "della", "delle", "con", "per", "sono", "una", "gli", "nel"}),
    "fr": frozenset({"les", "des", "une", "dans", "pour", "avec", "est", "sont", "sur"}),
    "de": frozenset({"der", "die", "das", "und", "mit", "für", "von", "ist", "sind"}),
    "es": frozenset({"los", "las", "una", "para", "con", "del", "por", "son", "como"}),
    "pt": frozenset({"uma", "para", "com", "dos", "das", "por", "são", "como", "que"}),
    "nl": frozenset({"het", "een", "van", "voor", "met", "zijn", "dat", "deze", "als"}),
    "pl": frozenset({"oraz", "jest", "dla", "przez", "który", "które", "nie", "się", "jako"}),
}


@dataclass(frozen=True, slots=True)
class DetectedLanguage:
    language: str
    confidence: float
    reason: str


def normalize_language_tag(value: str | None) -> str:
    raw = (value or "").strip().casefold().replace("_", "-")
    if not raw:
        return "und"
    if raw in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[raw]
    tag = raw.split("-", 1)[0]
    if tag in _LANGUAGE_ALIASES:
        return _LANGUAGE_ALIASES[tag]
    return tag if re.fullmatch(r"[a-z]{2,3}", tag) else "und"


def detect_language(text: str, *, metadata_language: str | None = None) -> DetectedLanguage:
    metadata = normalize_language_tag(metadata_language)
    if metadata != "und":
        content_detection = detect_language(text)
        if (
            content_detection.language != "und"
            and content_detection.language != metadata
            and content_detection.confidence >= 0.65
        ):
            return DetectedLanguage(
                content_detection.language,
                min(0.9, content_detection.confidence),
                f"metadata_content_conflict:{metadata}",
            )
        return DetectedLanguage(metadata, 0.98, "document_metadata")

    sample = text[:20_000]
    script_counts = {
        "ja": len(re.findall(r"[\u3040-\u30ff]", sample)),
        "ko": len(re.findall(r"[\uac00-\ud7af]", sample)),
        "zh": len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", sample)),
        "ar": len(re.findall(r"[\u0600-\u06ff]", sample)),
        "he": len(re.findall(r"[\u0590-\u05ff]", sample)),
        "el": len(re.findall(r"[\u0370-\u03ff]", sample)),
        "ru": len(re.findall(r"[\u0400-\u04ff]", sample)),
        "th": len(re.findall(r"[\u0e00-\u0e7f]", sample)),
    }
    script, count = max(script_counts.items(), key=lambda item: item[1])
    if count >= 8:
        # Han in Japanese text is secondary to Kana; Kana is checked first.
        if script == "zh" and script_counts["ja"] >= 3:
            script = "ja"
        return DetectedLanguage(script, min(0.99, 0.8 + count / 1000), "unicode_script")

    words = re.findall(r"[^\W\d_]+", sample.casefold(), flags=re.UNICODE)
    scores = Counter(
        {lang: sum(word in hints for word in words) for lang, hints in _LATIN_HINTS.items()}
    )
    language, score = scores.most_common(1)[0] if scores else ("und", 0)
    runner_up = scores.most_common(2)[1][1] if len(scores) > 1 else 0
    if score >= 3 and score >= runner_up + 1:
        return DetectedLanguage(language, min(0.9, 0.55 + score / 30), "content_function_words")
    return DetectedLanguage("und", 0.0, "insufficient_signal")


def language_execution_summary(store: Any, run_id: Any, *, contract: Any = None) -> dict[str, Any]:
    candidates = store.list_search_candidates(run_id)
    snapshots = store.list_snapshots_for_run(run_id)
    tool_queries = [
        item.input_summary.strip()
        for item in store.list_tool_executions(run_id)
        if item.tool_name == "web_search" and item.input_summary.strip()
    ]
    unique_queries = list(
        dict.fromkeys(
            [*tool_queries, *(item.query.strip() for item in candidates if item.query.strip())]
        )
    )
    planned_variants = {
        " ".join(item.query.casefold().split()): normalize_language_tag(item.language)
        for item in (contract.language_strategy.query_variants if contract is not None else [])
    }

    def _query_language(query: str) -> str:
        exact = planned_variants.get(" ".join(query.casefold().split()))
        if exact is not None:
            return exact
        from deepscout_research.contracts.evidence_relevance import planned_query_language

        return planned_query_language(query, contract)

    query_languages = Counter(_query_language(query) for query in unique_queries)
    source_languages = Counter(
        normalize_language_tag((item.retrieval_metadata or {}).get("original_language"))
        for item in snapshots
    )
    evidence_languages: Counter[str] = Counter()
    cross_language_evidence = 0
    output_language = normalize_language_tag(
        contract.output_language if contract is not None else "und"
    )
    for evidence in store.list_evidence(run_id):
        snapshot = store.get_snapshot(evidence.snapshot_id)
        language = normalize_language_tag(
            (snapshot.retrieval_metadata or {}).get("original_language") if snapshot else None
        )
        evidence_languages[language] += 1
        if language not in {"und", output_language}:
            cross_language_evidence += 1
    planned = contract.language_strategy if contract is not None else None
    return {
        "output_language": output_language,
        "planned_query_languages": (
            [planned.primary_query_language, *planned.additional_query_languages]
            if planned is not None
            else []
        ),
        "expected_primary_source_languages": (
            planned.expected_primary_source_languages if planned is not None else []
        ),
        "actual_query_languages": dict(query_languages),
        "query_strategy_transitions": [
            {
                "query_language": _query_language(query),
                "query_fingerprint": hashlib.sha256(query.encode()).hexdigest()[:12],
            }
            for query in unique_queries
        ],
        "source_languages": dict(source_languages),
        "evidence_languages": dict(evidence_languages),
        "cross_language_evidence_count": cross_language_evidence,
        "translation_operations": 0,
        "translation_path": "report_synthesis_model_derived_presentation",
    }
