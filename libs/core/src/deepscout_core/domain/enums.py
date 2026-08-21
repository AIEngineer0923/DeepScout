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
    INDEX = "index"
    EXTRACT = "extract"
    VERIFY = "verify"
    CONTRADICTION = "contradiction"
    COMPILE_KNOWLEDGE = "compile_knowledge"
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
    INDEXER = "indexer"
    EXTRACTOR = "extractor"
    VERIFIER = "verifier"
    CONTRADICTION = "contradiction"
    CRITIC = "critic"
    SYNTHESIS = "synthesis"
    REPORT = "report"
    EVALUATOR = "evaluator"


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


class IndexingStatus(StrEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    PARTIALLY_INDEXED = "partially_indexed"
    FAILED = "failed"
    SKIPPED = "skipped"


class WikiPageType(StrEnum):
    TOPIC = "topic"
    ENTITY = "entity"
    CONCEPT = "concept"
    FINDING = "finding"
    CONTRADICTION = "contradiction"
    QUESTION = "question"


class WikiPageStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    SUPERSEDED = "superseded"


class WikiChangeOp(StrEnum):
    CREATE = "create"
    CONFIRM = "confirm"
    REFINE = "refine"
    CONTRADICT = "contradict"
    SUPERSEDE = "supersede"
    MARK_STALE = "mark_stale"
    NO_CHANGE = "no_change"


class WikiStatementStatus(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    SUPERSEDED = "superseded"
    CONTRADICTED = "contradicted"


class WikiLinkType(StrEnum):
    RELATED_TO = "related_to"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"
    MENTIONS = "mentions"


class KnowledgeRelationType(StrEnum):
    SUPPORTS = "supports"
    REFUTES = "refutes"
    CONTRADICTS = "contradicts"
    CONFIRMS = "confirms"
    SUPERSEDES = "supersedes"
    RELATED_TO = "related_to"


class KnowledgeProvenanceKind(StrEnum):
    DETERMINISTIC = "deterministic"
    LLM_INFERRED = "llm_inferred"


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


class ReviewReasonCode(StrEnum):
    BUDGET_EXTENSION = "budget_extension"
    PRIVILEGED_TOOL = "privileged_tool"
    EXTERNAL_WRITE = "external_write"
    DESTRUCTIVE_OPERATION = "destructive_operation"
    GLOBAL_KNOWLEDGE_PROMOTION = "global_knowledge_promotion"
    KNOWLEDGE_DELETION = "knowledge_deletion"
    SECURITY_SENSITIVE_ACTION = "security_sensitive_action"
    MANUAL_USER_REQUEST = "manual_user_request"
    HUMAN_INPUT_REQUIRED = "human_input_required"


class ReviewRiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ReviewRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"
    RESPONDED = "responded"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


class ReviewDecisionKind(StrEnum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    RESPOND = "respond"


class HumanFeedbackTarget(StrEnum):
    REPORT = "report"
    CLAIM = "claim"
    EVIDENCE = "evidence"
    RETRIEVAL = "retrieval"
    OVERALL = "overall"
