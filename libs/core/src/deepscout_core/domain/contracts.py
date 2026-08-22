"""Research and report contracts — structured representation of user intent and deliverables."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

CONTRACT_SCHEMA_VERSION = "1"


class SourceConstraintMode(StrEnum):
    PREFER = "prefer"
    REQUIRE = "require"
    ONLY = "only"
    EXCLUDE = "exclude"


class SourceClass(StrEnum):
    OFFICIAL_INSTITUTIONAL = "official_institutional"
    PRIMARY_LEGISLATION = "primary_legislation"
    REGULATOR = "regulator"
    PEER_REVIEWED = "peer_reviewed"
    RESEARCH_BODY = "research_body"
    GOVERNMENT_STATISTICS = "government_statistics"
    MANUFACTURER_ENGINEERING = "manufacturer_engineering"
    FINANCIAL_FILING = "financial_filing"
    SOFTWARE_VENDOR = "software_vendor"
    NEWS_MEDIA = "news_media"
    INDUSTRY_BLOG = "industry_blog"
    UNKNOWN = "unknown"


class AuthorityClass(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    TERTIARY = "tertiary"
    UNKNOWN = "unknown"


class EvidenceStandard(StrEnum):
    AUTHORITATIVE = "authoritative"
    PEER_REVIEWED = "peer_reviewed"
    CREDIBLE = "credible"
    ANY = "any"


class RequirementKind(StrEnum):
    FACT = "fact"
    COMPARISON = "comparison"
    QUANTIFICATION = "quantification"
    DISTINCTION = "distinction"
    TIMELINE = "timeline"
    METHODOLOGY = "methodology"
    TRADEOFF = "tradeoff"
    DEPENDENCY = "dependency"
    SYNTHESIS = "synthesis"


class RequirementCoverageStatus(StrEnum):
    NOT_RESEARCHED = "not_researched"
    SEARCHED = "searched"
    SEARCHED_NO_EVIDENCE = "searched_no_evidence"
    EVIDENCE_FOUND = "evidence_found"
    SUPPORTED = "supported"
    PARTIAL = "partial"
    CONFLICTING = "conflicting"
    UNSUPPORTED = "unsupported"


class ClaimSupportState(StrEnum):
    SUPPORTED = "supported"
    PARTIALLY_SUPPORTED = "partially_supported"
    CONFLICTING = "conflicting"
    INSUFFICIENT = "insufficient"
    NOT_VERIFIED = "not_verified"


class ReportType(StrEnum):
    FACT_FINDING = "fact_finding"
    COMPARISON = "comparison"
    REGULATORY_ANALYSIS = "regulatory_analysis"
    SCIENTIFIC_REVIEW = "scientific_review"
    TECHNICAL_TRADEOFF = "technical_tradeoff"
    MARKET_ANALYSIS = "market_analysis"
    TEMPORAL_UPDATE = "temporal_update"
    MULTI_HOP = "multi_hop"
    EVIDENCE_REVIEW = "evidence_review"
    DECISION_SUPPORT = "decision_support"
    GENERAL_RESEARCH = "general_research"


class FinalCriticVerdict(StrEnum):
    PASS = "pass"
    REVISION_REQUIRED = "revision_required"
    RESEARCH_GAP = "research_gap"
    BLOCKED_BY_EVIDENCE = "blocked_by_evidence"


class TemporalRelation(StrEnum):
    APPLIES_FROM = "applies_from"
    ENFORCEABLE_FROM = "enforceable_from"
    TRANSITION_UNTIL = "transition_until"
    MUST_COMPLY_BY = "must_comply_by"
    ENTERED_INTO_FORCE = "entered_into_force"
    SUPERSEDED_FROM = "superseded_from"


class RetrievalFailureClass(StrEnum):
    """Diagnostic failure classes for retrieval and evidence pipelines."""

    SEARCH_DID_NOT_SURFACE_SOURCE = "search_did_not_surface_source"
    SOURCE_FETCH_FAILED = "source_fetch_failed"
    SOURCE_NOT_ADMISSIBLE = "source_not_admissible"
    ENTITY_EXTRACTION_FAILED = "entity_extraction_failed"
    ENTITY_NOT_CURRENT = "entity_not_current"
    EVIDENCE_NOT_VERIFIED = "evidence_not_verified"
    LEGAL_REFERENCE_UNRESOLVED = "legal_reference_unresolved"
    ROUTING_FAILURE = "routing_failure"
    LEXICAL_RETRIEVAL_FAILURE = "lexical_retrieval_failure"
    DENSE_RETRIEVAL_FAILURE = "dense_retrieval_failure"
    FUSION_FAILURE = "fusion_failure"
    RERANK_FAILURE = "rerank_failure"
    GRAPH_RETRIEVAL_FAILURE = "graph_retrieval_failure"
    COMPILED_KNOWLEDGE_FAILURE = "compiled_knowledge_failure"
    PROVENANCE_FAILURE = "provenance_failure"
    NO_ANSWER_FALSE_POSITIVE = "no_answer_false_positive"
    NO_ANSWER_FALSE_NEGATIVE = "no_answer_false_negative"
    CONTENT_EXTRACTION_FAILURE = "content_extraction_failure"


class LegalReference(BaseModel):
    instrument: str = Field(default="", max_length=500)
    article: str = Field(default="", max_length=64)
    paragraph: str = Field(default="", max_length=64)
    topic: str = Field(default="", max_length=500)
    source_url: str = Field(default="", max_length=2048)


class TemporalClaim(BaseModel):
    subject: str = Field(default="", max_length=500)
    obligation: str = Field(default="", max_length=1000)
    temporal_relation: TemporalRelation
    date_text: str = Field(default="", max_length=64)
    applicability_scope: str = Field(default="", max_length=500)
    evidence_quote: str = Field(default="", max_length=2000)
    source_url: str = Field(default="", max_length=2048)
    verified: bool = False


class OfficeHolderEvidence(BaseModel):
    person_name: str = Field(default="", max_length=200)
    office_title: str = Field(default="", max_length=300)
    institution: str = Field(default="", max_length=300)
    current_role_indicator: bool = False
    evidence_span: str = Field(default="", max_length=2000)
    source_url: str = Field(default="", max_length=2048)


class VerifiedEntity(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(default="", max_length=300)
    institution: str = Field(default="", max_length=300)
    evidence_id: str = Field(default="", max_length=64)
    source_url: str = Field(default="", max_length=2048)
    task_key: str = Field(default="", max_length=64)


class SourceAdmissionState(StrEnum):
    DISCOVERED = "discovered"
    FETCHED = "fetched"
    ADMISSIBLE = "admissible"
    EVIDENCE = "evidence"
    CITED = "cited"
    REJECTED = "rejected"


class SourceConstraint(BaseModel):
    mode: SourceConstraintMode
    scope: Literal["domain", "class", "publisher", "url"] = "class"
    values: list[str] = Field(default_factory=list, max_length=30)
    reason: str = Field(default="", max_length=500)


class AnswerRequirement(BaseModel):
    requirement_id: str = Field(min_length=1, max_length=32)
    text: str = Field(min_length=1, max_length=2000)
    kind: RequirementKind = RequirementKind.FACT
    critical: bool = True
    depends_on: list[str] = Field(default_factory=list, max_length=10)
    quantification_required: bool = False
    coverage_status: RequirementCoverageStatus = RequirementCoverageStatus.NOT_RESEARCHED
    coverage_note: str = Field(default="", max_length=2000)


class ResearchContract(BaseModel):
    schema_version: str = CONTRACT_SCHEMA_VERSION
    primary_question: str = Field(min_length=1, max_length=8000)
    user_intent: str = Field(default="", max_length=4000)
    output_language: str = Field(default="en", min_length=2, max_length=16)
    evidence_standard: EvidenceStandard = EvidenceStandard.CREDIBLE
    requirements: list[AnswerRequirement] = Field(default_factory=list, max_length=30)
    source_constraints: list[SourceConstraint] = Field(default_factory=list, max_length=20)
    preferred_source_classes: list[SourceClass] = Field(default_factory=list, max_length=10)
    required_source_classes: list[SourceClass] = Field(default_factory=list, max_length=10)
    forbidden_source_classes: list[SourceClass] = Field(default_factory=list, max_length=10)
    geography: list[str] = Field(default_factory=list, max_length=10)
    required_distinctions: list[str] = Field(default_factory=list, max_length=15)
    required_comparisons: list[str] = Field(default_factory=list, max_length=10)
    required_quantification: list[str] = Field(default_factory=list, max_length=10)
    required_timeframes: list[str] = Field(default_factory=list, max_length=10)
    uncertainty_requirements: list[str] = Field(default_factory=list, max_length=10)
    user_facing_questions: list[str] = Field(default_factory=list, max_length=15)


class ReportSectionSpec(BaseModel):
    section_id: str = Field(min_length=1, max_length=32)
    heading: str = Field(min_length=1, max_length=200)
    purpose: str = Field(default="", max_length=500)
    required: bool = True


class ReportContract(BaseModel):
    schema_version: str = CONTRACT_SCHEMA_VERSION
    report_type: ReportType = ReportType.GENERAL_RESEARCH
    title: str = Field(min_length=1, max_length=512)
    executive_summary_required: bool = True
    sections: list[ReportSectionSpec] = Field(default_factory=list, max_length=20)
    include_chronology: bool = False
    include_comparisons: bool = False
    include_quantitative_results: bool = False
    include_uncertainty_section: bool = True
    include_limitations_section: bool = True
    citation_mode: Literal["numbered", "inline"] = "numbered"
    include_sources_cited: bool = True
    include_sources_consulted: bool = False
    include_questions_answered: bool = False


class SourceAuthorityMetadata(BaseModel):
    source_class: SourceClass = SourceClass.UNKNOWN
    authority_class: AuthorityClass = AuthorityClass.UNKNOWN
    primary_vs_secondary: Literal["primary", "secondary", "unknown"] = "unknown"
    institutional: bool = False
    peer_reviewed: bool = False
    official: bool = False
    domain: str = Field(default="", max_length=255)
    publisher: str = Field(default="", max_length=255)


class CoverageMapEntry(BaseModel):
    requirement_id: str
    status: RequirementCoverageStatus
    note: str = Field(default="", max_length=2000)
    supporting_claim_ids: list[str] = Field(default_factory=list, max_length=20)


class CoverageMap(BaseModel):
    entries: list[CoverageMapEntry] = Field(default_factory=list, max_length=30)
    critical_unresolved: list[str] = Field(default_factory=list, max_length=15)
    material_gaps: list[str] = Field(default_factory=list, max_length=15)


class FinalCriticResult(BaseModel):
    verdict: FinalCriticVerdict
    issues: list[str] = Field(default_factory=list, max_length=20)
    reason_codes: list[str] = Field(default_factory=list, max_length=20)
    revision_notes: str = Field(default="", max_length=4000)
    unresolved_requirements: list[str] = Field(default_factory=list, max_length=15)
