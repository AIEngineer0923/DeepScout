"""DeepScout domain model (LangChain-independent)."""

from deepscout_core.domain.budget import (
    BudgetConsumption,
    BudgetExhaustedError,
    BudgetLedger,
    BudgetLedgerEntry,
    ResearchBudget,
)
from deepscout_core.domain.enums import (
    TERMINAL_RESEARCH_RUN_STATUSES,
    VERIFIED_CLAIM_STATUSES,
    BudgetMetric,
    ClaimVerificationStatus,
    ResearchQuestionStatus,
    ResearchRunStatus,
    SourceType,
    ToolExecutionStatus,
)
from deepscout_core.domain.invariants import DomainInvariantError
from deepscout_core.domain.schemas import (
    ClaimWrite,
    ContradictionWrite,
    DecisionWrite,
    EvidenceWrite,
    ReportWrite,
    ResearchPlanWrite,
    ResearchQuestionRead,
    ResearchRunCreate,
    ResearchRunRead,
    SourceSnapshotWrite,
    SourceWrite,
    ToolExecutionWrite,
)

__all__ = [
    "BudgetConsumption",
    "BudgetExhaustedError",
    "BudgetLedger",
    "BudgetLedgerEntry",
    "BudgetMetric",
    "ClaimVerificationStatus",
    "ClaimWrite",
    "ContradictionWrite",
    "DecisionWrite",
    "DomainInvariantError",
    "EvidenceWrite",
    "ReportWrite",
    "ResearchBudget",
    "ResearchPlanWrite",
    "ResearchQuestionRead",
    "ResearchQuestionStatus",
    "ResearchRunCreate",
    "ResearchRunRead",
    "ResearchRunStatus",
    "SourceSnapshotWrite",
    "SourceType",
    "SourceWrite",
    "TERMINAL_RESEARCH_RUN_STATUSES",
    "ToolExecutionStatus",
    "ToolExecutionWrite",
    "VERIFIED_CLAIM_STATUSES",
]
