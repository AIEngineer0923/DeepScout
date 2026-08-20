"""Domain enums and status taxonomies for DeepScout research."""

from enum import StrEnum


class ResearchRunStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BUDGET_EXHAUSTED = "budget_exhausted"


TERMINAL_RESEARCH_RUN_STATUSES: frozenset[ResearchRunStatus] = frozenset(
    {
        ResearchRunStatus.COMPLETED,
        ResearchRunStatus.FAILED,
        ResearchRunStatus.CANCELLED,
        ResearchRunStatus.BUDGET_EXHAUSTED,
    }
)


class ResearchQuestionStatus(StrEnum):
    PENDING = "pending"
    RESEARCHING = "researching"
    ANSWERED = "answered"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    SKIPPED = "skipped"


TERMINAL_RESEARCH_QUESTION_STATUSES: frozenset[ResearchQuestionStatus] = frozenset(
    {
        ResearchQuestionStatus.ANSWERED,
        ResearchQuestionStatus.INSUFFICIENT_EVIDENCE,
        ResearchQuestionStatus.SKIPPED,
    }
)


class ContradictionEvidenceStatus(StrEnum):
    SUFFICIENT = "sufficient"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class ResearchPhase(StrEnum):
    PLAN = "plan"
    RESEARCH = "research"
    COLLECT = "collect"
    FETCH = "fetch"
    EXTRACT = "extract"
    VERIFY = "verify"
    CONTRADICTION = "contradiction"
    CRITIC = "critic"
    SYNTHESIS = "synthesis"
    REPORT = "report"


class ResearchTaskStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


TERMINAL_RESEARCH_TASK_STATUSES: frozenset[ResearchTaskStatus] = frozenset(
    {
        ResearchTaskStatus.COMPLETED,
        ResearchTaskStatus.FAILED,
        ResearchTaskStatus.CANCELLED,
    }
)


class ResearchJobType(StrEnum):
    EXECUTE_RUN = "execute_run"
    RESUME_RUN = "resume_run"


class ResearchJobStatus(StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRole(StrEnum):
    PLANNER = "planner"
    SUPERVISOR = "supervisor"
    RESEARCH_WORKER = "research_worker"
    FETCH = "fetch"
    EXTRACTOR = "extractor"
    VERIFIER = "verifier"
    CONTRADICTION = "contradiction"
    CRITIC = "critic"
    SYNTHESIS = "synthesis"
    REPORT = "report"


class UsageReportStatus(StrEnum):
    UNKNOWN = "unknown"
    PARTIAL = "partial"
    COMPLETE = "complete"


class CostReportStatus(StrEnum):
    UNKNOWN = "unknown"
    ESTIMATED = "estimated"
    KNOWN = "known"


class ClaimVerificationStatus(StrEnum):
    PENDING = "pending"
    SUPPORTED = "supported"
    VERIFIED = "verified"
    PARTIALLY_VERIFIED = "partially_verified"
    REFUTED = "refuted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


VERIFIED_CLAIM_STATUSES: frozenset[ClaimVerificationStatus] = frozenset(
    {
        ClaimVerificationStatus.VERIFIED,
        ClaimVerificationStatus.PARTIALLY_VERIFIED,
    }
)


class SourceType(StrEnum):
    WEB = "web"
    UPLOAD = "upload"
    MANUAL = "manual"


class BudgetMetric(StrEnum):
    ITERATIONS = "iterations"
    WALL_TIME = "wall_time"
    TOKENS = "tokens"
    COST = "cost"
    SOURCES = "sources"
    TOOL_CALLS = "tool_calls"


class ToolExecutionStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
