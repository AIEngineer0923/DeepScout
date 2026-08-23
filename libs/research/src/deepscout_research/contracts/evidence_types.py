"""Conservative evidence-type classification from source and explicit text signals."""

from __future__ import annotations

from deepscout_core.domain.contracts import EvidenceType, SourceAuthorityMetadata, SourceClass


def classify_evidence_type(
    *,
    source: SourceAuthorityMetadata,
    title: str = "",
    text: str = "",
) -> EvidenceType:
    combined = f"{title} {text}".casefold()
    if source.source_class in {SourceClass.PRIMARY_LEGISLATION, SourceClass.REGULATOR}:
        return EvidenceType.LEGISLATION_REGULATION
    if source.source_class == SourceClass.NEWS_MEDIA:
        return EvidenceType.SECONDARY_REPORTING
    if any(token in combined for token in ("opinion", "commentary", "editorial", "perspective")):
        return EvidenceType.OPINION_COMMENTARY
    if any(token in combined for token in ("meta-analysis", "systematic review", "literature review")):
        return EvidenceType.REVIEW_META_ANALYSIS
    if any(token in combined for token in ("simulation", "modelled", "modeled", "scenario model")):
        return EvidenceType.MODEL_SIMULATION
    if any(token in combined for token in ("field observation", "observed in situ", "surveyed", "monitoring")):
        return EvidenceType.OBSERVATIONAL
    if any(token in combined for token in ("experiment", "experimental", "controlled trial", "field trial")):
        return EvidenceType.EXPERIMENT
    if source.source_class == SourceClass.PEER_REVIEWED and any(
        token in combined for token in ("methods", "results", "study", "measured", "measurement")
    ):
        return EvidenceType.PRIMARY_EMPIRICAL
    if source.source_class == SourceClass.OFFICIAL_INSTITUTIONAL:
        return EvidenceType.INSTITUTIONAL_GUIDANCE
    if source.source_class in {SourceClass.MANUFACTURER_ENGINEERING, SourceClass.FINANCIAL_FILING}:
        return EvidenceType.COMPANY_CLAIM
    return EvidenceType.UNKNOWN
