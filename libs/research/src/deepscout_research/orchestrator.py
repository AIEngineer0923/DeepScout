"""Research orchestrator — deterministic supervisor with parallel workers."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from deepscout_core.domain.budget import BudgetExhaustedError
from deepscout_core.domain.enums import (
    ResearchPhase,
    ResearchQuestionStatus,
    ResearchRunStatus,
    ResearchTaskStatus,
)
from deepscout_core.domain.events import ResearchEvent, ResearchEventType
from deepscout_core.settings import Settings
from deepscout_persistence.session import get_session_factory
from deepscout_persistence.store import ResearchStore
from langsmith import traceable

from deepscout_research.budget_gate import BudgetGate
from deepscout_research.exceptions import RunCancelledError
from deepscout_research.phases.contradiction import detect_contradictions_for_run
from deepscout_research.phases.critic import run_critic_for_run
from deepscout_research.phases.extract import extract_claims_for_run
from deepscout_research.phases.fetch import fetch_sources_for_run
from deepscout_research.phases.report import generate_report
from deepscout_research.phases.synthesis import synthesize_decision
from deepscout_research.phases.verify import verify_claims_for_run
from deepscout_research.planner import build_research_plan, planner_output_to_write
from deepscout_research.search.protocol import WebSearchProvider
from deepscout_research.tasks.graph import TaskGraph
from deepscout_research.termination import TerminationDecision, evaluate_termination
from deepscout_research.workers.pool import ResearchWorkerPool

logger = logging.getLogger(__name__)

EventSink = Callable[[ResearchEvent], None]


@dataclass
class OrchestratorResult:
    run_id: uuid.UUID
    final_status: ResearchRunStatus
    iterations: int
    events: list[ResearchEvent] = field(default_factory=list)


class ResearchOrchestrator:
    """Global deterministic supervisor — bounded workers execute ready tasks."""

    def __init__(
        self,
        store: ResearchStore,
        settings: Settings,
        search_provider: WebSearchProvider,
        *,
        event_sink: EventSink | None = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self._search = search_provider
        self._budget = BudgetGate(store)
        self._events: list[ResearchEvent] = []
        self._sink = event_sink
        self._max_correction_rounds = 1

    def _ensure_active(self, run_id: uuid.UUID) -> None:
        run = self._store.get_run(run_id)
        if run is not None and run.status == ResearchRunStatus.CANCELLED:
            raise RunCancelledError(f"Research run {run_id} cancelled")

    def _emit(self, event: ResearchEvent) -> None:
        self._events.append(event)
        if self._sink is not None:
            self._sink(event)
        self._store.append_run_event(
            event.run_id,
            event.event_type.value,
            {
                "phase": event.phase.value if event.phase else None,
                "iteration": event.iteration,
                **(event.payload or {}),
            },
        )

    @traceable(name="research_run_execute", run_type="chain")
    def execute(self, run_id: uuid.UUID) -> OrchestratorResult:
        run = self._store.get_run(run_id)
        if run is None:
            raise LookupError(f"ResearchRun {run_id} not found")

        self._store.update_run_status(run_id, ResearchRunStatus.RUNNING)
        self._store.reclaim_stale_running_tasks(
            run_id, stale_after_seconds=self._settings.research_task_stale_after_s
        )
        self._emit(ResearchEvent(event_type=ResearchEventType.RUN_STARTED, run_id=run_id))

        iterations = 0
        try:
            self.build_plan(run_id, goal=run.goal)
            while True:
                self._ensure_active(run_id)
                iterations += 1
                decision = self.execute_research_batch(run_id, iteration=iterations)
                if decision.should_stop:
                    break

            self._ensure_active(run_id)
            self._run_post_research_phases(run_id)

            final = evaluate_termination(
                budget=run.budget,
                consumption=self._store.get_consumption(run_id),
                questions=self._store.list_questions(run_id),
                tasks=self._store.list_tasks(run_id),
            )
            terminal_status = (
                final.terminal_status if final.should_stop else ResearchRunStatus.COMPLETED
            )
            reason = final.reason if final.should_stop else "pipeline_complete"
            self._store.set_termination_reason(run_id, reason)
            self._store.update_run_status(run_id, terminal_status)
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.RUN_COMPLETED,
                    run_id=run_id,
                    payload={"reason": reason},
                )
            )
            return OrchestratorResult(
                run_id=run_id,
                final_status=terminal_status,
                iterations=iterations,
                events=list(self._events),
            )
        except RunCancelledError:
            self._store.set_termination_reason(run_id, "cancelled")
            self._store.update_run_status(run_id, ResearchRunStatus.CANCELLED)
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.RUN_CANCELLED,
                    run_id=run_id,
                    payload={"reason": "cancelled"},
                )
            )
            return OrchestratorResult(
                run_id=run_id,
                final_status=ResearchRunStatus.CANCELLED,
                iterations=iterations,
                events=list(self._events),
            )
        except BudgetExhaustedError:
            if self._settings.research_finalize_on_budget_exhausted:
                try:
                    self._ensure_active(run_id)
                    self._run_post_research_phases(run_id)
                except RunCancelledError:
                    self._store.set_termination_reason(run_id, "cancelled")
                    self._store.update_run_status(run_id, ResearchRunStatus.CANCELLED)
                    return OrchestratorResult(
                        run_id=run_id,
                        final_status=ResearchRunStatus.CANCELLED,
                        iterations=iterations,
                        events=list(self._events),
                    )
                except Exception:
                    logger.exception(
                        "Finalization after budget exhaustion failed",
                        extra={"run_id": str(run_id)},
                    )
            self._store.set_termination_reason(run_id, "budget_exhausted")
            self._store.update_run_status(run_id, ResearchRunStatus.BUDGET_EXHAUSTED)
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.RUN_COMPLETED,
                    run_id=run_id,
                    payload={"reason": "budget_exhausted"},
                )
            )
            return OrchestratorResult(
                run_id=run_id,
                final_status=ResearchRunStatus.BUDGET_EXHAUSTED,
                iterations=iterations,
                events=list(self._events),
            )
        except Exception:
            logger.exception("Research run failed", extra={"run_id": str(run_id)})
            self._store.set_termination_reason(run_id, "unexpected_failure")
            self._store.update_run_status(run_id, ResearchRunStatus.FAILED)
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.RUN_FAILED,
                    run_id=run_id,
                    payload={"error": "unexpected_failure"},
                )
            )
            return OrchestratorResult(
                run_id=run_id,
                final_status=ResearchRunStatus.FAILED,
                iterations=iterations,
                events=list(self._events),
            )

    @traceable(name="phase:plan", run_type="chain")
    def build_plan(self, run_id: uuid.UUID, *, goal: str) -> None:
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.PLAN,
            )
        )
        run = self._store.get_run(run_id)
        if run is None:
            raise LookupError(f"ResearchRun {run_id} not found")

        if self._store.list_questions(run_id):
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.PHASE_COMPLETED,
                    run_id=run_id,
                    phase=ResearchPhase.PLAN,
                )
            )
            return

        budget_summary = (
            f"iterations={run.budget.max_iterations}, "
            f"sources={run.budget.max_sources}, "
            f"tool_calls={run.budget.max_tool_calls}"
        )
        plan_output = build_research_plan(
            self._settings,
            run_id=run_id,
            goal=goal,
            budget_summary=budget_summary,
            output_language=run.output_language,
            store=self._store,
        )
        self._store.save_plan(run_id, planner_output_to_write(plan_output))
        self._store.commit()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.PLAN,
            )
        )

    def execute_research_batch(self, run_id: uuid.UUID, *, iteration: int) -> TerminationDecision:
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.RESEARCH,
                iteration=iteration,
            )
        )
        run = self._store.get_run(run_id)
        if run is None:
            raise LookupError(f"ResearchRun {run_id} not found")

        tasks = self._store.list_tasks(run_id)
        if not tasks or self._settings.research_use_legacy_path:
            return self._legacy_single_question_iteration(run_id, iteration=iteration)

        graph = TaskGraph(tuple(tasks))
        graph.validate_dependencies()
        ready = graph.ready_tasks()
        for task in ready:
            if task.status == ResearchTaskStatus.PENDING:
                self._store.update_task_status(task.id, ResearchTaskStatus.READY)

        consumption = self._store.get_consumption(run_id)
        pre_decision = evaluate_termination(
            budget=run.budget,
            consumption=consumption,
            questions=self._store.list_questions(run_id),
            tasks=self._store.list_tasks(run_id),
        )
        if pre_decision.should_stop:
            return pre_decision

        if not ready:
            return evaluate_termination(
                budget=run.budget,
                consumption=self._store.get_consumption(run_id),
                questions=self._store.list_questions(run_id),
                tasks=self._store.list_tasks(run_id),
            )

        self._store.commit()
        self._budget.reserve_iteration(run_id, note=f"iteration:{iteration}")
        self._store.commit()
        pool = ResearchWorkerPool(
            get_session_factory(self._settings.database_url),
            self._settings,
            self._search,
            max_workers=self._store.get_concurrency_limit(run_id),
            inline_store=self._store if self._settings.research_workers_inline else None,
        )
        results = pool.execute_batch(run_id, ready, iteration=iteration)
        self._store.refresh()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.RESEARCH,
                iteration=iteration,
                payload={"workers": len(results), "ready_tasks": len(ready)},
            )
        )
        return evaluate_termination(
            budget=run.budget,
            consumption=self._store.get_consumption(run_id),
            questions=self._store.list_questions(run_id),
            tasks=self._store.list_tasks(run_id),
        )

    def _legacy_single_question_iteration(
        self, run_id: uuid.UUID, *, iteration: int
    ) -> TerminationDecision:
        """Backward-compatible path when no task rows exist."""
        from urllib.parse import urlparse

        from deepscout_core.domain.schemas import (
            SearchCandidateWrite,
            SourceWrite,
        )

        from deepscout_research.fetch.secure import public_http_url_or_none

        run = self._store.get_run(run_id)
        if run is None:
            raise LookupError(f"ResearchRun {run_id} not found")
        consumption = self._store.get_consumption(run_id)
        questions = self._store.list_questions(run_id)
        pre_decision = evaluate_termination(
            budget=run.budget,
            consumption=consumption,
            questions=questions,
        )
        if pre_decision.should_stop:
            return pre_decision
        self._budget.reserve_iteration(run_id, note=f"iteration:{iteration}")
        pending = [q for q in questions if q.status == ResearchQuestionStatus.PENDING]
        if not pending:
            return evaluate_termination(
                budget=run.budget,
                consumption=self._store.get_consumption(run_id),
                questions=self._store.list_questions(run_id),
            )
        question = pending[0]
        self._store.update_question_status(question.id, ResearchQuestionStatus.RESEARCHING)
        query = question.text[:500]
        try:
            results = self._search.search(query, max_results=3)
            self._budget.reserve_tool_call(run_id, note=f"search:{iteration}")
        except Exception:
            self._store.update_question_status(
                question.id, ResearchQuestionStatus.INSUFFICIENT_EVIDENCE
            )
            return evaluate_termination(
                budget=run.budget,
                consumption=self._store.get_consumption(run_id),
                questions=self._store.list_questions(run_id),
            )
        self._store.add_search_candidates(
            run_id,
            SearchCandidateWrite(
                query=query,
                provider=self._search.provider_name,
                results=results,
                question_id=question.id,
            ),
        )
        for result in results:
            safe_url = public_http_url_or_none(result.url)
            if safe_url is None:
                continue
            domain = urlparse(safe_url).netloc
            _, created = self._store.add_source(
                run_id,
                SourceWrite(canonical_url=safe_url, title=result.title, domain=domain),
            )
            if created:
                try:
                    self._budget.reserve_source(run_id, note=f"iteration:{iteration}")
                except BudgetExhaustedError:
                    return TerminationDecision(
                        should_stop=True,
                        reason="budget_exhausted",
                        terminal_status=ResearchRunStatus.BUDGET_EXHAUSTED,
                    )
        self._store.update_question_status(question.id, ResearchQuestionStatus.ANSWERED)
        return evaluate_termination(
            budget=run.budget,
            consumption=self._store.get_consumption(run_id),
            questions=self._store.list_questions(run_id),
        )

    def _run_post_research_phases(self, run_id: uuid.UUID) -> None:
        run = self._store.get_run(run_id)
        if run is None:
            return

        self._ensure_active(run_id)
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.FETCH,
            )
        )
        try:
            fetched = fetch_sources_for_run(
                self._store, run_id, max_sources=min(5, run.budget.max_sources)
            )
        except Exception:
            logger.exception("Fetch phase failed", extra={"run_id": str(run_id)})
            fetched = 0
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.FETCH,
                payload={"snapshots_created": fetched},
            )
        )
        self._store.commit()

        self._ensure_active(run_id)
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.EXTRACT,
            )
        )
        try:
            extract_stats = extract_claims_for_run(self._store, run_id)
        except Exception:
            logger.exception("Extract phase failed", extra={"run_id": str(run_id)})
            extract_stats = {"claims_created": 0, "evidence_created": 0}
        self._store.commit()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.EXTRACT,
                payload=extract_stats,
            )
        )

        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.VERIFY,
            )
        )
        try:
            verify_stats = verify_claims_for_run(self._store, run_id)
        except Exception:
            logger.exception("Verify phase failed", extra={"run_id": str(run_id)})
            verify_stats = {}
        self._store.commit()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.VERIFY,
                payload=verify_stats,
            )
        )

        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.CONTRADICTION,
            )
        )
        try:
            contradictions = detect_contradictions_for_run(self._store, run_id)
        except Exception:
            logger.exception("Contradiction phase failed", extra={"run_id": str(run_id)})
            contradictions = 0
        self._store.commit()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.CONTRADICTION,
                payload={"contradictions_detected": contradictions},
            )
        )

        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.CRITIC,
            )
        )
        claims = self._store.list_claims(run_id)
        critic_result = None
        if claims:
            critic_result = run_critic_for_run(self._store, run_id)
            correction_round = 0
            while (
                not critic_result.passed
                and correction_round < self._max_correction_rounds
            ):
                correction_round += 1
                self._ensure_active(run_id)
                verify_claims_for_run(self._store, run_id)
                critic_result = run_critic_for_run(self._store, run_id)
        else:
            from deepscout_core.domain.schemas import CriticResult

            critic_result = CriticResult(
                passed=True,
                artifact_type="research_pipeline",
                severity="pass",
                issues=[],
            )
        self._store.commit()
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.CRITIC,
                payload={
                    "passed": critic_result.passed,
                    "issues": critic_result.issues,
                },
            )
        )

        decision_id = None
        if critic_result.passed:
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.PHASE_STARTED,
                    run_id=run_id,
                    phase=ResearchPhase.SYNTHESIS,
                )
            )
            try:
                decision_id = synthesize_decision(self._store, self._settings, run_id)
            except Exception:
                logger.exception("Synthesis phase failed", extra={"run_id": str(run_id)})
            self._store.commit()
            self._emit(
                ResearchEvent(
                    event_type=ResearchEventType.PHASE_COMPLETED,
                    run_id=run_id,
                    phase=ResearchPhase.SYNTHESIS,
                    payload={"decision_id": str(decision_id) if decision_id else None},
                )
            )

        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_STARTED,
                run_id=run_id,
                phase=ResearchPhase.REPORT,
            )
        )
        report_id = generate_report(self._store, run_id)
        self._emit(
            ResearchEvent(
                event_type=ResearchEventType.PHASE_COMPLETED,
                run_id=run_id,
                phase=ResearchPhase.REPORT,
                payload={"report_id": str(report_id)},
            )
        )
