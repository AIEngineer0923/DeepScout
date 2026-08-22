"""Research quality contracts package."""

from deepscout_research.contracts.coverage import evaluate_coverage, gap_search_queries
from deepscout_research.contracts.evidence_relevance import (
    claim_specificity_allowed,
    is_evidence_relevant,
    relevance_score,
)
from deepscout_research.contracts.extract import (
    build_research_contract,
    contract_from_snapshot,
    derive_report_contract,
    report_contract_from_snapshot,
)
from deepscout_research.contracts.source_authority import (
    admission_state_for_source,
    classify_source_authority,
    enrich_search_query_with_policy,
    is_source_admissible,
    violates_only_constraint,
)

__all__ = [
    "admission_state_for_source",
    "build_research_contract",
    "claim_specificity_allowed",
    "classify_source_authority",
    "contract_from_snapshot",
    "derive_report_contract",
    "enrich_search_query_with_policy",
    "evaluate_coverage",
    "gap_search_queries",
    "is_evidence_relevant",
    "is_source_admissible",
    "report_contract_from_snapshot",
    "relevance_score",
    "violates_only_constraint",
]
